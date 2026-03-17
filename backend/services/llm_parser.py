import os
import json

import google.generativeai as genai

API_KEY = "AIzaSyDBobAsT9CHEtowGwAaeL697wb4xhd-SIY"
MODEL_NAME = "models/gemini-2.5-flash"
genai.configure(api_key=API_KEY)


def parse_with_llm(full_text: str, identifier_json: dict):

    document_family = identifier_json.get("document_family")
    document_subtype = identifier_json.get("document_subtype")

    identity = identifier_json.get("identity_markers", {})
    table_identity = identity.get("transaction_table_identity", {})

    table_headers = table_identity.get("table_header_markers", [])
    has_running_balance = table_identity.get("presence_of_running_balance", False) 
    debit_credit_style = table_identity.get("debit_credit_style", False)

    prompt = f"""
You are a deterministic financial transaction extraction engine.

DOCUMENT TYPE:
{document_family}

DOCUMENT SUBTYPE:
{document_subtype}

KNOWN TABLE STRUCTURE:
Headers: {table_headers}
Has Running Balance: {has_running_balance}
Debit/Credit Style: {debit_credit_style}

You MUST follow this known structure.
Do NOT re-classify the document.
Do NOT infer new structure.

-------------------------------------------------------
EXTRACTION RULES
-------------------------------------------------------

1. Extract EVERY transaction row across ALL pages.
2. A transaction row MUST begin with a valid date.
3. If a line does not begin with a date but is aligned under narration,
   append it to previous transaction.
4. Ignore summary rows (Opening Balance, Total, Grand Total, etc.)
5. Preserve chronological order exactly.

-------------------------------------------------------
BALANCE HANDLING
-------------------------------------------------------
-------------------------------------------------------
BALANCE HANDLING
-------------------------------------------------------

If Has Running Balance = True:
    Extract running balance strictly from the balance column.
    Do NOT infer balance from last numeric value.

Else:
    balance must be null.
-------------------------------------------------------
DEBIT / CREDIT HANDLING
-------------------------------------------------------

If Debit/Credit Style = True:
    Use separate debit and credit columns strictly by header position.
    Never shift values between columns.
    Never use balance column as debit or credit.

If Debit/Credit Style = False:

    If statement_type == INVESTMENT_STATEMENT:
        Map primary transaction Amount column to debit only.
        credit must be null.
        Ignore NAV, Units, Price, Load, Percentage,
        Balance Units or valuation-related columns.

    Else:

        In single Amount column layouts:
            - Extract ONLY the amount present in the same row as the date.
            - Do NOT use numbers from side panels or summary sections.
            - Do NOT use totals, outstanding, statement balance,
              previous balance, minimum due, or header values.

        Infer using keywords in the row narration:
            DR, Withdrawal, Purchase, Spent, EMI → debit
            CR, Deposit, Refund, Payment, Credit, Cashback → credit

        If no credit keyword is present:
            Treat the row amount as debit.

Debit and credit cannot both be non-null.
If Has Running Balance = False:
    balance must be null.
Balance must never be copied into debit or credit.

-------------------------------------------------------
STRICT OUTPUT FORMAT
-------------------------------------------------------

Return STRICT VALID JSON array only.
No explanation.
No markdown.

[
  {{
    "date": "DD-MM-YYYY",
    "details": "exact narration text",
    "debit": number or null,
    "credit": number or null,
    "balance": number or null,
    "confidence": number between 0 and 1
  }}
]

------------------------------------------------------------------------------------------------------------
DOCUMENT TEXT:
{full_text}
"""

    model = genai.GenerativeModel(MODEL_NAME)

    response = model.generate_content(
       prompt,
       generation_config={
        "temperature": 0
    })

    llm_response = response.text.strip()
    return llm_response