import os
import re
import json
import google.generativeai as genai
from typing import List, Dict, Any

MODEL_NAME = "models/gemini-2.5-flash"

def generate_extraction_logic_llm(identifier_json: dict, *args, **kwargs) -> str:
    text_sample = kwargs.get("text_sample", "")
    if args:
        if len(args) >= 2:
            text_sample = args[1]
        elif len(args) == 1:
            text_sample = args[0]
            
    document_family = identifier_json.get("document_family")
    document_subtype = identifier_json.get("document_subtype")
 
    identity = identifier_json.get("identity_markers", {})
    table_identity = identity.get("transaction_table_identity", {})
 
    table_headers = table_identity.get("table_header_markers", [])
    minimum_column_count = table_identity.get("minimum_column_count", 0)
    has_running_balance = table_identity.get("presence_of_running_balance", False)
    debit_credit_style = table_identity.get("debit_credit_style", False)
 
   
    family_behavior_block = f"""
---------------------------------------------------------
DOCUMENT FAMILY ADAPTATION RULES (CRITICAL)
---------------------------------------------------------
 
The parsing strategy MUST adapt based on Document Family.
 
If Document Family is one of:
 
- DEMAT_STATEMENT
- INVESTMENT_STATEMENT
- FIXED_DEPOSIT_STATEMENT
- RECURRING_DEPOSIT_STATEMENT
- PENSION_STATEMENT
- INSURANCE_POLICY_STATEMENT
- BROKERAGE_CONTRACT_NOTE
- GENERIC_STATEMENT_OF_ACCOUNT
 
Then:
 
• Do NOT assume debit/credit ledger format.
• Do NOT assume running balance exists.
• Do NOT enforce minimum_column_count >= 5 rule.
• If date-based transaction rows do not exist,
  extract structured financial rows based on:
    - ISIN / Units / NAV / Quantity / Amount columns
    - Holding rows
    - Investment transaction rows
    - Buy/Sell rows
• If no monetary ledger rows exist,
  return empty list safely without error.
 
If Document Family is:
 
- BANK_ACCOUNT_STATEMENT
- CREDIT_CARD_STATEMENT
- OVERDRAFT_CASH_CREDIT_STATEMENT
- WALLET_STATEMENT
- PAYMENT_GATEWAY_SETTLEMENT
- TAX_LEDGER_STATEMENT
- FOREX_STATEMENT
- ESCROW_STATEMENT
 
Then:
 
• Apply strict ledger parsing logic.
• Date detection is mandatory.
• Monetary value must exist.
 
The generated code must NEVER crash
if structure does not match ledger pattern.
 
"""
    bank_statement_prompt  = f"""
You are a Senior Python Backend Engineer specializing in financial document parsing.

Your task is to generate COMPLETE, VALID, and EXECUTABLE Python code.

You must generate EXACTLY one function:

    def extract_transactions(text: str) -> list:

The function must parse financial transaction rows from raw document text.

The code must be deterministic.
The code must not rely on guessing.
The code must not use LLM inside.
The code must not contain placeholders.

Return ONLY Python code.
No markdown.
No explanation.
No comments outside code.

---------------------------------------------------------
STRUCTURAL CONTEXT
---------------------------------------------------------

Document Family: {document_family}
Document Subtype: {document_subtype}

Table Headers:
{table_headers}

Minimum Column Count:
{minimum_column_count}

Has Running Balance:
{has_running_balance}

Debit Credit Style:
{debit_credit_style}

{family_behavior_block}

---------------------------------------------------------
PARSING REQUIREMENTS
---------------------------------------------------------

1️⃣ DATE DETECTION

Transaction row MUST contain valid date near beginning.

Supported:
- DD/MM/YYYY
- DD-MM-YYYY
- DD.MM.YYYY
- DD/MM/YY
- DD-MM-YY
- DD-MMM-YYYY
- DD MMM YYYY
- YYYY-MM-DD
- D/M/YYYY

Use compiled regex.
Use re.search.
No named groups.

Row MUST also contain at least one valid monetary value.

---------------------------------------------------------

2️⃣ MULTI-LINE HANDLING

If no date but transaction open:
    append to details
    preserve spacing

---------------------------------------------------------

3️⃣ MONEY REGEX

MONEY_REGEX = r'\\d+(?:,\\d{{2,3}})*(?:\\.\\d{{2}})'

Rules:
- Must contain decimal
- Ignore 4-digit years
- 0.00 should not be treated as transaction amount

---------------------------------------------------------

4️⃣ STRUCTURED PARSING (PRIORITY)

If minimum_column_count >= 5:

    Split using:
        re.split(r'\\s{{2,}}', line)

    Detect columns using flexible matching:

        withdrawal_column → header contains "withdraw"
        deposit_column → header contains "deposit"
        balance_column → header contains "balance"

    Case-insensitive.

    Extract ONLY from these columns.

    If withdrawal column has value > 0:
        debit = value

    If deposit column has value > 0:
        credit = value

    If Has Running Balance:
        balance = balance column value

    NEVER swap.
    NEVER infer by size.

---------------------------------------------------------

5️⃣ FALLBACK PARSING

If structured parsing does not assign debit or credit:

    Find all MONEY_REGEX matches.

    Remove 0.00 values from transaction candidates.

    If Has Running Balance:

        If at least 2 values:
            balance = rightmost value
            transaction_amount = second rightmost

        Determine side using balance delta:

            If previous_balance exists:

                If balance < previous_balance:
                    debit = transaction_amount

                If balance > previous_balance:
                    credit = transaction_amount

            Else:
                Use keywords:
                    DR, Debit, Withdrawal → debit
                    CR, Credit, Deposit, Refund → credit

    Else:

        If only one value:
            Use keywords to assign side.

---------------------------------------------------------

6️⃣ MANDATORY SINGLE-SIDE ENFORCEMENT (CRITICAL)

Before appending transaction:

    If both debit and credit are None:
        If transaction_amount exists:
            Assign side using:

                If Has Running Balance and previous_balance exists:
                    Use balance delta

                Else:
                    Default to debit

    If both debit and credit are populated:
        Keep the one that matches balance delta.
        Set the other to None.

    Ensure:
        EXACTLY ONE of debit or credit must be non-null
        for every valid transaction row.

---------------------------------------------------------

7️⃣ STRICT PRECEDENCE

1. Structured column mapping
2. Running balance delta
3. Keyword inference
4. Final mandatory enforcement

---------------------------------------------------------

8️⃣ FILTERING

Skip row if:
- No monetary value
- Starts with:
    Opening Balance
    Closing Balance
    B/F
    Forwarded
    Total
    Summary
    Grand Total

---------------------------------------------------------

9️⃣ OUTPUT FORMAT

{{
    "date": str,
    "details": str,
    "debit": float or None,
    "credit": float or None,
    "balance": float or None,
    "confidence": float
}}

Confidence:

- 0.95 → structured mapping
- 0.93 → flexible header mapping
- 0.92 → balance delta mapping
- 0.85 → keyword fallback
- 0.80 → mandatory enforcement used

---------------------------------------------------------

10️⃣ SAFETY

- Maintain previous_balance
- Update after each row
- Wrap row parsing in try/except
- Never raise exception
- Always return list
- Preserve order

---------------------------------------------------------
INPUT TEXT:
---------------------------------------------------------
{text_sample}
"""
    credit_card_prompt = f"""
You are a Senior Python Backend Engineer specializing in financial document parsing.

Generate EXACTLY one function:

    def extract_transactions(text: str) -> list:

This function must parse DEBIT or CREDIT CARD statement transactions.

The function must extract ONLY real merchant purchases and payments.

The function must be deterministic.
The function must not use LLM internally.
Return ONLY Python code.
No markdown.
No explanation.
No comments outside code.

---------------------------------------------------------
CORE OBJECTIVE
---------------------------------------------------------

Extract ONLY:

• Merchant purchase transactions
• Refund transactions
• Payment transactions

DO NOT extract:

• Bank fees
• Markup charges
• Currency conversion rows
• Finance charges
• Interest rows
• EMI conversion rows
• Transfer rows
• Statement summary rows
• Total/Minimum Due rows
• Balance rows

---------------------------------------------------------
1️⃣ TRANSACTION STRUCTURE
---------------------------------------------------------

A row is valid ONLY IF:

1. Starts with optional whitespace + valid date.
2. Contains exactly one date.
3. Does NOT contain date-range pattern.
4. Contains at least one valid monetary value.
5. Length < 250 characters.

---------------------------------------------------------
2️⃣ DATE RULES
---------------------------------------------------------

Supported formats:

- DD/MM/YYYY
- DD-MM-YYYY
- DD-MMM-YYYY
- DD MMM YYYY
- YYYY-MM-DD
- D/M/YYYY

Date must start within first 30 characters.
If more than one date → reject.
If date range exists → reject.

---------------------------------------------------------
3️⃣ MONEY RULES
---------------------------------------------------------

MONEY_REGEX = r'\\d+(?:,\\d{{2,3}})*(?:\\.\\d{{2}})'

• Extract all matches.
• Remove 0.00.
• Remove 4-digit year-like numbers.
• If none remain → reject.
• Use rightmost as transaction amount.

---------------------------------------------------------
4️⃣ STRICT SUMMARY REJECTION
---------------------------------------------------------

If FULL LINE contains whole-word:

    Due
    Total
    Minimum
    Limit
    Interest
    Calculation
    Number
    Remaining
    Opening
    Closing
    Statement
    Amount
    Balance

→ Reject immediately.

---------------------------------------------------------
5️⃣ NON-MERCHANT EVENT REJECTION
---------------------------------------------------------

Reject row if details contain whole-word:

    TRANSFERRED
    TRANSFER
    MARKUP
    CONVERSION
    FINANCE
    INTEREST
    FOREIGN
    FEE
    CHARGE

These are bank/internal events, not merchant purchases.

---------------------------------------------------------
6️⃣ DETAILS EXTRACTION
---------------------------------------------------------

Extract substring between:

    end of date
    and start of rightmost monetary match.

Normalize spaces.

Reject if:

• Empty
• < 3 characters
• > 70% numeric

---------------------------------------------------------
7️⃣ DEBIT / CREDIT
---------------------------------------------------------

If two monetary values:

    First → debit
    Second → credit

If one value:

    If description contains:

        PAYMENT
        PAY
        UPI
        REFUND
        REVERSAL
        CASHBACK
        CREDIT
        CR

    → credit
    Else → debit

Exactly ONE must be populated.

---------------------------------------------------------
8️⃣ CONFIDENCE
---------------------------------------------------------

If description contains EMI → 0.90
Else → 0.95

---------------------------------------------------------
9️⃣ RULES
---------------------------------------------------------

• balance must always be None.
• Never infer running balance.
• Skip malformed rows.
• Wrap parsing in try/except.
• Never raise exception.
• Always return list.
• Preserve chronological order.

---------------------------------------------------------
INPUT TEXT:
---------------------------------------------------------
{text_sample}
"""

    if document_family == "CREDIT_CARD_STATEMENT":
        prompt = credit_card_prompt
    else:
        prompt = bank_statement_prompt


    model = genai.GenerativeModel(MODEL_NAME)
 
    response = model.generate_content(
        prompt,
        generation_config={
                "temperature": 0
    })
 
    content = response.text.strip()
    if content is None:
        raise ValueError("LLM returned empty extraction code.")
 
    raw_output = content.strip()
 
    if "```" in raw_output:
        parts = raw_output.split("```")
        raw_output = parts[1] if len(parts) > 1 else parts[0]
 
    raw_output = raw_output.strip()
 
    if raw_output.lower().startswith("python"):
        raw_output = raw_output[6:].strip()
 
    return raw_output

def _sanitize_text(text: str) -> str:
    """Replace problematic Unicode characters with ASCII equivalents."""
    replacements = {
        '\u20b9': 'Rs',   # ₹
        '\u20ac': 'EUR',  # €
        '\u00a3': 'GBP',  # £
        '\u2018': "'",    # '
        '\u2019': "'",    # '
        '\u201c': '"',    # "
        '\u201d': '"',    # "
        '\u2013': '-',    # –
        '\u2014': '-',    # —
        '\u00a0': ' ',    # non-breaking space
        '\u200b': '',     # zero-width space
        '\u200c': '',     # zero-width non-joiner
        '\u200d': '',     # zero-width joiner
        '\ufeff': '',     # BOM
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text


def extract_transactions_using_logic(
    full_text: str,
    extraction_code: str
) -> List[Dict]:
 
    try:
        cleaned_code = extraction_code.strip()
 
        if "```" in cleaned_code:
            parts = cleaned_code.split("```")
            cleaned_code = parts[1] if len(parts) > 1 else parts[0]
 
        cleaned_code = cleaned_code.strip()

        # Remove python language marker if present
        if cleaned_code.lower().startswith("python"):
            cleaned_code = cleaned_code[6:].strip()  # type: ignore

        # Sanitize the code itself
        cleaned_code = _sanitize_text(cleaned_code)

        # Sanitize the input PDF text to prevent encoding errors inside the function
        safe_text = _sanitize_text(full_text)

        from datetime import datetime
        import json
        import io
        import sys

        from typing import Any
        execution_namespace: Dict[str, Any] = {
            "re": re,
            "List": List,
            "Dict": Dict,
            "datetime": datetime,
            "json": json,
        }

        # Redirect stdout during exec to avoid charmap print crashes
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

        try:
            exec(cleaned_code, execution_namespace)
        finally:
            sys.stdout = old_stdout
 
        if "extract_transactions" not in execution_namespace:
            raise ValueError("extract_transactions function not found.")
 
        extract_fn = execution_namespace["extract_transactions"]

        # Redirect stdout during function execution too
        sys.stdout = io.StringIO()
        try:
            transactions = extract_fn(safe_text)
        finally:
            sys.stdout = old_stdout
 
        if not isinstance(transactions, list):
            raise ValueError("Extraction must return List[Dict].")

        # Sanitize all string values in output transactions
        for txn in transactions:
            for key, val in txn.items():
                if isinstance(val, str):
                    txn[key] = _sanitize_text(val)

        print(f"\nExtracted {len(transactions)} transactions.")
        for i, txn in enumerate(transactions[:5], 1):  # type: ignore
            safe_repr = {k: str(v).encode('ascii', 'replace').decode('ascii') for k, v in txn.items()}
            print(f"{i}: {safe_repr}")
        return transactions
 
    except Exception as e:
        raise RuntimeError(f"LLM extraction execution failed: {str(e)}")