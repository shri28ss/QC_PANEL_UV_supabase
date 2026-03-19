
import json
def safe_json_loads(data):
    if isinstance(data, (dict, list)): return data
    if isinstance(data, str):
        try: return safe_json_loads(data)
        except: return None
    return data
import re
import json
import os
from typing import Dict, List, Tuple
from repository.statement_category_repo import (
    get_under_review_formats,
    insert_statement_category
)

# ============================================================
# ================== CONFIG ==================
# ============================================================

import google.generativeai as genai

API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL_NAME= "models/gemini-2.5-flash"
genai.configure(api_key=API_KEY)

def reduce_text(pages: List[str]) -> Dict:
    return {
        "first_page": pages[0][:6000] if pages else "",  # type: ignore
        "last_page": pages[-1][-3000:] if pages else "",  # type: ignore
        "headers": [
            line.strip()
            for p in pages
            for line in p.splitlines()
            if re.search(r"\b(Date|Debit|Credit|Balance|Amount)\b", line, re.I)
        ][:10]  # type: ignore
    }

# ============================================================
# ================== UNIVERSAL MATCH ENGINE (COLAB EXACT) ====
# ============================================================

def evaluate_identity_markers(identity: Dict, text: str):

    text_norm = re.sub(r"\s+", " ", text.lower())

    scores = {"total_score": 0.0, "total_max": 0.0}

    def process_rule(rule_obj, key_path, weight=5):

        if not rule_obj:
            return

        if isinstance(rule_obj, list) and rule_obj:
            scores["total_max"] += weight
            matched = any(isinstance(k, str) and k.lower() in text_norm for k in rule_obj)
            if matched:
                scores["total_score"] += weight
            return

        if not isinstance(rule_obj, dict):
            return

        rule_type = rule_obj.get("rule")

        if rule_type == "keyword":
            patterns = rule_obj.get("patterns", [])
            if not patterns:
                return

            scores["total_max"] += weight
            matched = any(p.lower() in text_norm for p in patterns)
            if matched:
                scores["total_score"] += weight

        elif rule_type == "regex":
            pattern = rule_obj.get("pattern")
            if not pattern:
                return

            scores["total_max"] += weight
            matched = bool(re.search(pattern, text, re.I))
            if matched:
                scores["total_score"] += weight

    # Traverse structure
    for section_name, section in identity.items():
        if not isinstance(section, dict):
           continue

        for field_name, field_value in section.items():
            key_path = f"{section_name}.{field_name}"
            if isinstance(field_value, dict) and "rule" not in field_value:
                for sub_name, sub_value in field_value.items():
                    process_rule(sub_value, f"{key_path}.{sub_name}")
            else:
                process_rule(field_value, key_path)

    # TABLE HEADER FUZZY (HIGH WEIGHT)
    table = identity.get("transaction_table_identity", {})
    headers = table.get("table_header_markers", [])
    min_required = table.get("minimum_column_count", 0)

    if headers:
        weight = 25
        scores["total_max"] += weight

        text_compact = re.sub(r"\s+", "", text.lower())

        matched_count = sum(
            1 for h in headers
            if re.sub(r"\s+", "", h.lower()) in text_compact
        )

        if matched_count >= min_required:
            scores["total_score"] += (matched_count / len(headers)) * weight

    # FOOTER
    footer = identity.get("footer_identity", {})
    footer_patterns = footer.get("footer_markers", [])

    if footer_patterns:
        weight = 5
        scores["total_max"] += weight
        matched = any(
            re.search(p, text, re.I) if "\\" in p else p.lower() in text_norm
            for p in footer_patterns
        )
        if matched:
            scores["total_score"] += weight

    total_max = scores["total_max"]
    total_score = scores["total_score"]
    confidence = round(float((total_score / total_max) * 100), 2) if total_max else 0.0  # type: ignore
    return confidence

# ============================================================
# ================== DB MATCH (REPLACES REGISTRY) ============
# ============================================================

def find_existing_identifier(text: str, threshold: float = 80.0):
    # User Request: Every PDF should be treated individually even if they have the same format.
    # Bypassing the format check so that each document gets its own extraction logic and statement category.
    return False, None

    from typing import Any
    best: Dict[str, Any] = {"identifier": None, "score": 0.0}
    categories = get_under_review_formats()

    for cat in categories:

        identifier_json = cat.get("statement_identifier")

        if isinstance(identifier_json, str):
            identifier_json = safe_json_loads(identifier_json)

        identity = identifier_json.get("identity_markers", {})

        score = evaluate_identity_markers(identity, text)

        if score > best["score"]:
            best = {
                "category": cat,
                "score": score
            }

    if best["score"] >= threshold:
        return True, best["category"]

    return False, None

# ============================================================
# ================== LLM CLASSIFICATION (COLAB EXACT) ========
# ============================================================

def classify_document_llm(reduced: Dict):

    prompt = """
You are a Senior Financial Document Classification Engine
and Universal Financial Identity Extraction System.

Your task has TWO PARTS:

PART 1 → Classify the financial document
PART 2 → Extract structural identity markers

Use ONLY the provided text.
Do NOT guess.
If insufficient evidence → classify as UNKNOWN_FINANCIAL_DOCUMENT.

============================================================
PART 1 — DOCUMENT CLASSIFICATION
============================================================

------------------------------------------------------------
LEVEL 1 — DOCUMENT FAMILY (choose EXACTLY ONE)
------------------------------------------------------------

1. BANK_ACCOUNT_STATEMENT
2. CREDIT_CARD_STATEMENT
3. LOAN_STATEMENT
4. OVERDRAFT_CASH_CREDIT_STATEMENT
5. WALLET_STATEMENT
6. PAYMENT_GATEWAY_SETTLEMENT
7. INVESTMENT_STATEMENT
8. DEMAT_STATEMENT
9. TAX_LEDGER_STATEMENT
10. FIXED_DEPOSIT_STATEMENT
11. RECURRING_DEPOSIT_STATEMENT
12. INSURANCE_POLICY_STATEMENT
13. PENSION_STATEMENT
14. BROKERAGE_CONTRACT_NOTE
15. FOREX_STATEMENT
16. ESCROW_STATEMENT
17. GENERIC_STATEMENT_OF_ACCOUNT
18. UNKNOWN_FINANCIAL_DOCUMENT

------------------------1 LOAN_STATEMENT--------------------
If ANY appear → MUST classify as LOAN_STATEMENT:
 
• Loan Account Number
• Loan A/c No
• EMI
• Equated Monthly Installment
• Principal Outstanding
• Principal Repaid
• Interest Charged (loan context)
• Interest Rate
• Sanction Amount
• Disbursement
• Repayment Schedule
• Installment Due Date
• Overdue Amount
• Total Loan Outstanding
• Amortization Schedule
 
If EMI OR Principal Outstanding exists → STOP → LOAN_STATEMENT
 
Do NOT classify as BANK if loan markers exist.
---------------------2 CREDIT_CARD_STATEMENT----------------
If ANY appear → CREDIT_CARD_STATEMENT:
 
• Masked card number (XXXX-XXXX-1234)
• Minimum Amount Due
• Total Amount Due
• Payment Due Date
• Credit Limit
• Available Credit
• Revolving Credit
• Finance Charges
• Cash Advance Limit
 
Credit card always has:
• Statement Date
• Due Date
• Total Due
 
If those 3 exist together → CREDIT_CARD_STATEMENT
----------------------3 DEMAT_STATEMENT---------------------
If ANY appear → DEMAT_STATEMENT:
 
• DP ID
• BO ID
• Beneficial Owner
• Depository Participant
• NSDL
• CDSL
• ISIN Code
• Transaction cum Holding Statement
• Holding Statement
• Pledge Balance
• Free Balance (securities context)
• Lock-in securities
 
If ISIN column exists → STOP → DEMAT_STATEMENT
If DP ID + ISIN both exist → STOP → DEMAT_STATEMENT
-----------------4 OVERDRAFT_CASH_CREDIT_STATEMENT----------
If ANY appear:
 
• Drawing Power
• DP
• Sanctioned Limit
• CC Limit
• OD Limit
• Limit Utilized
• Available Limit
• Cash Credit Account
• CC Account
• OD Account
• Margin Requirement
• Hypothecation
• Stock Statement
• Interest on CC
 
AND running balance ledger exists
 
→ MUST classify as OVERDRAFT_CASH_CREDIT_STATEMENT
 
Do NOT classify as BANK if limit structure present.
-------------------5 TAX_LEDGER_STATEMENT-------------------
If ANY appear → TAX_LEDGER_STATEMENT:
 
• GSTIN
• Electronic Cash Ledger
• Electronic Credit Ledger
• Electronic Liability Register
• Input Tax Credit
• Output Tax
• CGST / SGST / IGST
• GSTR
• Tax Period
• Challan Identification Number (CIN in GST context)
 
If GSTIN + Tax Period + CGST/SGST present → TAX_LEDGER_STATEMENT
-------------------6 PAYMENT_GATEWAY_SETTLEMENT-------------------
If ANY appear → PAYMENT_GATEWAY_SETTLEMENT:
 
• Merchant Settlement Report
• Settlement ID
• Settlement Date
• MDR (Merchant Discount Rate)
• Commission
• Net Settlement
• Gross Collection
• Gateway Charges
• Payment Processor (Razorpay, PayU, Stripe, etc.)
 
If settlement batch structure exists → classify here.
-----------------7 INVESTMENT_STATEMENT---------------------
If ANY appear → INVESTMENT_STATEMENT:
 
• Portfolio Summary
• Asset Allocation
• NAV
• Units Held
• Fund Name
• Mutual Fund
• Equity Portfolio
• SIP
• Market Value (portfolio context)
 
If NAV + Units Held appear → INVESTMENT_STATEMENT
 
Do NOT confuse with DEMAT:
DEMAT has ISIN + DP ID
Investment has NAV + Units
-------------------8 FIXED_DEPOSIT_STATEMENT-------------------
If ANY appear → FIXED_DEPOSIT_STATEMENT:

• Fixed Deposit Account
• Term Deposit
• FD Account Number
• Maturity Date
• Maturity Amount
• Deposit Amount
• Interest Rate (FD context)
• Auto Renewal
• Deposit Tenure

FD has:
• No running debit/credit ledger
• Lump sum deposit
• Maturity value

Do NOT classify as BANK if FD structure exists.
-------------------9 RECURRING_DEPOSIT_STATEMENT-------------------
If ANY appear → RECURRING_DEPOSIT_STATEMENT:

• Recurring Deposit
• RD Account
• Monthly Installment (deposit context)
• Installment Paid
• Missed Installment
• RD Maturity Value
• RD Tenure

RD has:
• Fixed periodic contribution
• Maturity value
• No loan structure
-------------------10 INSURANCE_POLICY_STATEMENT-------------------
If ANY appear → INSURANCE_POLICY_STATEMENT:

• Policy Number
• Premium Due
• Premium Paid
• Sum Assured
• Surrender Value
• Nominee
• Policy Term
• Life Assured

Insurance has:
• Policy ID
• Premium schedule
• No debit/credit ledger
-------------------11 PENSION_STATEMENT-------------------
If ANY appear → PENSION_STATEMENT:

• UAN
• PF Account
• Employee Contribution
• Employer Contribution
• Pension Contribution
• PRAN
• Tier I / Tier II (NPS context)
• Accumulated Pension Wealth

Pension statements contain contribution summary, not transaction ledger.
-------------------12 BROKERAGE_CONTRACT_NOTE-------------------
If ANY appear → BROKERAGE_CONTRACT_NOTE:

• Contract Note
• Trade ID
• Order ID
• Execution Price
• Brokerage
• Securities Transaction Tax (STT)
• Exchange (NSE/BSE)
• Settlement Number

Contract note is trade confirmation, NOT demat holding.
Demat has ISIN + DP ID.
-------------------13 FOREX_STATEMENT-------------------
If ANY appear → FOREX_STATEMENT:

• Currency Pair
• Exchange Rate
• Remittance Reference
• Inward Remittance
• Outward Remittance
• SWIFT MT103
• Forex Conversion

Forex statement contains multi-currency transaction structure.
-------------------14 ESCROW_STATEMENT-------------------
If ANY appear → ESCROW_STATEMENT:

• Escrow Account
• Escrow Balance
• Trustee
• Beneficiary
• Escrow Agreement
• Disbursement from Escrow

Escrow is controlled trust account, not regular bank ledger.
-------------------15 GENERIC_STATEMENT_OF_ACCOUNT-------------------
If ANY appear → GENERIC_STATEMENT_OF_ACCOUNT:

• Statement of Account
• Outstanding Receivable
• Outstanding Payable
• Invoice Reference
• Ledger Balance (non-bank context)
• Vendor Statement
• Customer Statement

Used in corporate/vendor ledger context.
No banking, loan, demat, or tax structure.
------------------------------------------------------------
LEVEL 2 — DOCUMENT SUBTYPE
------------------------------------------------------------

Subtype MUST belong to selected Level 1.
If UNKNOWN_FINANCIAL_DOCUMENT → subtype must be UNKNOWN.

============================================================
PART 2 — UNIVERSAL IDENTITY MARKER EXTRACTION
============================================================

You must extract identity markers that uniquely define
this specific document structure.

These identity categories apply to ALL document families.

If a field does not exist in the document → return null or empty array.

------------------------------------------------------------
IDENTITY CATEGORIES (FOR ALL DOCUMENT TYPES)
------------------------------------------------------------

1️⃣ ISSUER / INSTITUTION IDENTITY
- issuer_name
- brand keywords
- regulatory identifiers regex MUST always be included
  (IFSC, SWIFT, IBAN, GSTIN, CIN, SEBI, RBI, NSDL, CDSL, etc.)
- merchant_id (if applicable)
- dp_id / bo_id (if applicable)

2️⃣ DOCUMENT STRUCTURE IDENTITY
- document_title_phrase
- document_type_keywords
- document_reference_number pattern
- report_generation_phrase

3️⃣ PERIOD / DATE IDENTITY
- statement_period pattern
- statement_date pattern
- billing_cycle pattern
- tax_period pattern

4️⃣ ACCOUNT / ENTITY IDENTITY
(Adapt dynamically based on document type)

Possible patterns include:
- account_number
- masked_card_number
- loan_account_number
- customer_id
- wallet_id
- merchant_id
- gstin
- pan
- bo_id
- dp_id

Use regex where structured.
Use keyword rules for static labels.

5️⃣ TRANSACTION TABLE IDENTITY
- exact header markers found
- minimum_column_count
- presence_of_running_balance (true/false)
- debit_credit_style (true/false)

6️⃣ FINANCIAL SUMMARY IDENTITY
- total_outstanding pattern
- minimum_due pattern
- emi_amount pattern
- credit_limit pattern
- drawing_power pattern
- portfolio_value pattern
- total_tax pattern

Only include patterns actually visible.

7️⃣ FOOTER / STATIC MARKER IDENTITY
- disclaimer phrases
- “system generated” markers
- page number format
- static regulatory lines

============================================================
INSTITUTION EXTRACTION RULES
============================================================

Extract exact issuing institution name from text.
If multiple entities → return issuing authority.
If not found → UNKNOWN.

============================================================
COUNTRY DETECTION
============================================================

Use:
- Currency symbol
- Regulatory identifiers
- IFSC → India
- IBAN → EU
- GSTIN → India
- Address format

If unclear → UNKNOWN.

============================================================
CONFIDENCE SCORING
============================================================

0.90 – 1.00 → Strong structural evidence
0.70 – 0.89 → Strong keyword evidence
0.50 – 0.69 → Moderate evidence
Below 0.50 → Weak

============================================================
DOCUMENT TEXT SAMPLE
============================================================

FIRST PAGE:
""" + reduced["first_page"] + """

LAST PAGE:
""" + reduced["last_page"] + """

TABLE HEADERS:
""" + json.dumps(reduced["headers"]) + """

OTHER TEXT:
""" + reduced.get("other_sample", "") + """

============================================================

STRICT RULES:
- No guessing
- No explanation
- No markdown
- Return STRICT valid JSON only
- Use null where field not present
- Subtype must match Level 1
- If unsure → UNKNOWN_FINANCIAL_DOCUMENT

STATEMENT VERSIONING:
- ID format: [document_family]_[document_subtype]_[VERSION]

============================================================
INSTRUCTIONS
============================================================

1. Identify institution, document type, and structural markers
2. Extract deterministic identity signals ONLY
3. Do NOT infer missing data
4. Prefer regex rules for structured fields
5. Use keyword rules for static phrases
6. Output MUST follow the exact format below
7. Do NOT include explanations
8. Do NOT include markdown
9. Return Python-style literals (None, True, False)

============================================================
REQUIRED OUTPUT FORMAT (STRICT)
============================================================

{
  "id": "UNIQUE_ID_V1",
  "document_family": "",
  "document_subtype": "",
  "institution_name": "",
  "country": "",
  "confidence_score": 0.0,

  "identity_markers": {

    "issuer_identity": {
      "issuer_name": { "rule": "keyword", "patterns": [] },
      "regulatory_identifiers": {
        "ifsc": { "rule": "regex", "pattern": "..." },
        "swift": { "rule": "regex", "pattern": "..." },
        "iban": { "rule": "regex", "pattern": "..." },
        "gstin": { "rule": "regex", "pattern": "..." },
        "other": []
      }
    },

    "document_structure_identity": {
      "document_title_phrase": { "rule": "keyword", "patterns": [] },
      "document_reference_number": { "rule": "regex", "pattern": None },
      "generation_phrase": { "rule": "keyword", "patterns": [] }
    },

    "period_identity": {
      "statement_period": { "rule": "regex", "pattern": None },
      "statement_date": { "rule": "regex", "pattern": None },
      "billing_cycle": { "rule": "regex", "pattern": None },
      "tax_period": { "rule": "regex", "pattern": None }
    },

    "entity_identity": {
      "account_number": { "rule": "regex", "pattern": None },
      "masked_card_number": { "rule": "regex", "pattern": None },
      "loan_account_number": { "rule": "regex", "pattern": None },
      "customer_id": { "rule": "regex", "pattern": None },
      "wallet_id": { "rule": "regex", "pattern": None },
      "merchant_id": { "rule": "regex", "pattern": None },
      "pan": { "rule": "regex", "pattern": None },
      "bo_id": { "rule": "regex", "pattern": None },
      "dp_id": { "rule": "regex", "pattern": None }
    },

    "transaction_table_identity": {
      "table_header_markers": ["Exact", "Column", "Names"],
      "minimum_column_count": 0,
      "presence_of_running_balance": False,
      "debit_credit_style": False
    },

    "financial_summary_identity": {
      "total_outstanding": { "rule": "regex", "pattern": None },
      "minimum_due": { "rule": "regex", "pattern": None },
      "emi_amount": { "rule": "regex", "pattern": None },
      "credit_limit": { "rule": "regex", "pattern": None },
      "drawing_power": { "rule": "regex", "pattern": None },
      "portfolio_value": { "rule": "regex", "pattern": None },
      "total_tax": { "rule": "regex", "pattern": None }
    },

    "footer_identity": {
      "footer_markers": []
    }
  }
}

============================================================
OUTPUT RULES
============================================================

• Return ONLY the object above
• Do NOT wrap in markdown
• Do NOT add explanations
• Use Python literals: None, True, False
"""

    model = genai.GenerativeModel(MODEL_NAME)

    response = model.generate_content(
        prompt,
        generation_config={
        "temperature": 0,
        "response_mime_type": "application/json"
    })

    raw_output = response.text.strip()

    # Normalize rare uppercase NULL
    raw_output = re.sub(r'\bNULL\b', 'null', raw_output)

    identifier = safe_json_loads(raw_output)

    return identifier

def derive_bank_code_from_identifier(identifier_json):
    """
    Extract first 4 characters from IFSC pattern if available.
    Returns None if IFSC not found or invalid.
    """

    try:
        ifsc_obj = (
            identifier_json
            .get("identity_markers", {})
            .get("issuer_identity", {})
            .get("regulatory_identifiers", {})
            .get("ifsc")
        )

        if not ifsc_obj:
            return None

        pattern = ifsc_obj.get("pattern")

        if not pattern:
            return None

        # If Gemini returned actual IFSC like HDFC0000501
        match = re.match(r"^([A-Z]{4})", pattern)
        if match:
            return match.group(1)

        return None

    except Exception:
        return None

def save_new_statement_format(
    format_name,
    bank_code,
    identifier_json,
    extraction_logic,
    threshold=65.0
):
    """
    Save only identifier JSON.
    statement_type and institution_name are auto-derived.
    """

    statement_type = identifier_json.get("document_family")
    institution_name = identifier_json.get("institution_name")
    bank_code = derive_bank_code_from_identifier(identifier_json)
    return insert_statement_category(
        statement_type=statement_type,
        format_name=format_name,
        institution_name=institution_name,
        ifsc_code=bank_code,
        identifier_json=identifier_json,
        extraction_logic=extraction_logic,
        threshold=threshold
    )