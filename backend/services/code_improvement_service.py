"""
Code Improvement Service.

Takes reconciliation feedback (flags, remarks, mismatches) along with the
current extraction code and PDF text, and asks the LLM to generate an
improved extraction function.
"""
import json
import ast
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

API_KEY = "AIzaSyBfdKSpLkGAx_1WOnlC-8mhn_SchDlULdg"
MODEL_NAME = "models/gemini-2.5-flash" # Verified SUCCESS model
genai.configure(api_key=API_KEY)

def _build_examples_block(llm_transactions: list, pdf_text: str) -> str:
    """
    Search for LLM-extracted transactions in the raw PDF text and return a 
    formatted examples block showing the line each transaction likely came from.
    """
    import re as _re
    lines = pdf_text.splitlines()
    examples = []
    
    # Limit to first 15 for prompt brevity
    for txn in llm_transactions[:15]:
        date_str = txn.get("date", "")
        amount = txn.get("debit") or txn.get("credit")
        if not date_str or amount is None:
            continue
            
        found_line = None
        # Try finding a line that contains both the date and the absolute value of the amount
        amt_str = f"{abs(float(amount)):,.2f}"
        for line in lines:
            if date_str in line and (amt_str in line or f"{abs(float(amount)):.2f}" in line):
                found_line = line.strip()
                break
        
        if found_line:
            examples.append(
                f"TARGET: {json.dumps(txn)}\n"
                f"MATCHING RAW LINE: \"{found_line}\"\n"
            )
            
    return "\n".join(examples) if examples else "No explicit line-mappings could be determined."



def build_improvement_prompt(
    current_code: str,
    code_transactions: list,
    llm_transactions: list,
    reconciliation: dict,
    remarks: dict,
    pdf_text: str,
    override_patterns: list = [],
) -> str:
    """Build the prompt for the LLM to improve extraction code."""

    matched = reconciliation.get("matched_pairs", [])
    field_flags = reconciliation.get("field_flags", [])
    unmatched_code = reconciliation.get("unmatched_code", [])
    unmatched_llm = reconciliation.get("unmatched_llm", [])
    overall_sim = reconciliation.get("overall_similarity", 0)
    summary = reconciliation.get("summary", {})

    n_code = reconciliation.get("summary", {}).get("total_code", 0)
    n_llm = reconciliation.get("summary", {}).get("total_llm", 0)
    n_match = reconciliation.get("summary", {}).get("matched_count", 0)
    current_accuracy = reconciliation.get("overall_similarity", 0)

    # ---- DIAGNOSIS block ----
    if n_code == 0:
        diagnosis = f"CRITICAL: The current code extracted ZERO transactions while LLM found {n_llm}. Current Accuracy: {current_accuracy}%"
    elif n_match == 0 and n_code > 0:
        diagnosis = f"CRITICAL: The code extracted {n_code} transactions, but NONE of them match the target truth (LLM found {n_llm}). Current Accuracy: {current_accuracy}%"
    else:
        diagnosis = f"The code is partially working but has mismatches. Matched: {n_match}/{n_llm}. Current Accuracy: {current_accuracy}%. You must fix the remaining {n_llm - n_match} unmatched rows."

    # ---- Build feedback section (SMART DELTA) ----
    feedback_lines = []
    
    trust_all_matches = remarks.get("global_trust_all_matches", "")
    
    # 1. Matched rows: INCLUDE ALL. Tag as perfect match or mismatch.
    for i, (pair, flags) in enumerate(zip(matched, field_flags)):
        remark_code = remarks.get(f"matched_code_{i}", "")
        remark_llm = remarks.get(f"matched_llm_{i}", "")
        remark = remark_code or remark_llm
        
        flag_str = ", ".join(flags.keys()) if flags else "none"

        line = (
            f"MATCHED ROW {i+1}:\n"
            f"  Code Output: {json.dumps(pair['code'])}\n"
            f"  LLM Target:  {json.dumps(pair['llm'])}\n"
        )
        
        if not remark and not flags:
            line += f"  STATUS: PERFECT MATCH (Keep this logic)\n"
        else:
            line += f"  STATUS: MISMATCH (Auto-flagged differences: {flag_str})\n"
            if remark:
                if "[TRUST_CODE]" in remark:
                    line += f"  ★★★ USER VERIFIED: THE CODE IS 100% CORRECT (IGNORE LLM). ★★★\n"
                elif "[TRUST_LLM]" in remark:
                    line += f"  ★★★ USER VERIFIED: THE LLM IS 100% CORRECT (UPDATE CODE TO MATCH THIS). ★★★\n"
                else:
                    line += f"  QC REMARK: \"{remark}\"\n"

        feedback_lines.append(line.rstrip())

    # 2. Unmatched in LLM (missing from code - code is wrong)
    for i, txn in enumerate(unmatched_llm):
        remark = remarks.get(f"unmatched_llm_{i}", "")
        line = f"UNMATCHED LLM ROW {i+1} (Missing from code output):\n  LLM Target: {json.dumps(txn)}\n"
        if remark:
            if "[TRUST_LLM]" in remark:
                line += f"  ★★★ USER VERIFIED: THIS ROW MUST BE EXTRACTED (UPDATE CODE TO CATCH THIS). ★★★\n"
            else:
                line += f"  QC REMARK: \"{remark}\"\n"
        else:
            line += f"  STATUS: CODE MISSED THIS (Update code to extract this).\n"
        feedback_lines.append(line.rstrip())

    # 3. Unmatched in Code (extra in code - potential garbage)
    for i, txn in enumerate(unmatched_code):
        remark = remarks.get(f"unmatched_code_{i}", "")
        line = f"UNMATCHED CODE ROW {i+1} (Extra row extracted by code):\n  Code Output: {json.dumps(txn)}\n"
        if remark:
            if "[TRUST_CODE]" in remark:
                line += f"  ★★★ USER VERIFIED: THIS EXTRACTION IS CORRECT (LLM MISSED IT, KEEP THIS CODE LOGIC). ★★★\n"
            elif "[TRUST_LLM]" in remark:
                line += f"  ★★★ USER VERIFIED: THIS IS GARBAGE/NOISE (UPDATE CODE TO IGNORE THIS). ★★★\n"
            else:
                line += f"  QC REMARK: \"{remark}\"\n"
        else:
            line += f"  STATUS: POTENTIAL GARBAGE (Unless user verified, code should probably not extract this).\n"
        feedback_lines.append(line.rstrip())

    feedback_block = "\n\n".join(feedback_lines) if feedback_lines else "No discrepancies or feedback provided."

    # Bulk Trust Context
    bulk_context = ""
    if trust_all_matches == "[TRUST_CODE_FOR_ALL_MATCHES]":
        bulk_context = "\n\n★★★ CRITICAL BULLETIN: USER HAS MARKED EVERY MATCHED ROW WITHOUT A REMARK AS 'TRUST_CODE'. THE CURRENT CODE LOGIC IS ALREADY WORKING WELL FOR THOSE ROWS. ★★★\n"
    elif trust_all_matches == "[TRUST_LLM_FOR_ALL_MATCHES]":
        bulk_context = "\n\n★★★ CRITICAL BULLETIN: USER HAS MARKED EVERY MATCHED ROW IN THIS PDF AS 'TRUST_LLM'. THE LLM VERSION IS THE TRUTH. ★★★\n"

    # Build systemic patterns section
    p_lines = []
    for i, p in enumerate(override_patterns, 1):
        line = (
            f"SYSTEMIC PATTERN {i} (Recurring errors from previous documents of this format):\n"
            f"  Field: {p['field_name']}\n"
            f"  Code usually extracts: {p.get('ai_value', 'N/A')}\n"
            f"  Correct value should be: {p.get('user_value', 'N/A')}\n"
        )
        p_lines.append(line)
    systemic_patterns_block = "\n".join(p_lines) if p_lines else "No format-wide systemic correction patterns discovered yet."

    # Global empty hint
    global_hint = remarks.get("global_empty", "")
    global_block = f"\n\nGLOBAL HINT FROM QC (CRITICAL CONTEXT):\n{global_hint}\n" if global_hint else ""

    prompt = f"""Update the following Python extraction function. You must bridge the gap between what the current code produces and the semantic truth.

DIAGNOSIS (Read this first):
{diagnosis}
{bulk_context}{global_block}
CURRENT FUNCTION:
=========================================
{current_code}
=========================================

CODE OUTPUT (All transactions extracted by current code):
{json.dumps(code_transactions, indent=2)}

REFERENCE TRUTH (All transactions correctly extracted by LLM):
{json.dumps(llm_transactions, indent=2)}

USER FEEDBACK & REMARKS (Instructions to fix):
{feedback_block}

SYSTEMIC PATTERNS (Format-wide corrections):
{systemic_patterns_block}

FULL EXTRACTED PDF TEXT (Use this to understand the exact row format and fix your parsing logic):
=========================================
{pdf_text}
=========================================

CONCRETE EXAMPLES — HOW EACH TARGET TRANSACTION MAPS TO A RAW PDF LINE:
(Find these dates/amounts in the PDF TEXT above to understand the exact pattern)
{_build_examples_block(llm_transactions, pdf_text)}

CRITICAL: The current code logic is failing on the rows marked MISMATCH or CODE MISSED THIS.
You MUST MODIFY the code to handle these edge cases. You are allowed to:
- Change the regex patterns.
- Add new condition checks or keywords.
- Reformulate the loop logic (e.g. handle multi-line transactions differently).
- Improve the column positioning or balance delta logic.

GUIDELINES FOR YOUR NEW CODE:
1. Setup:
   - Import `re` and `datetime` INSIDE the function.
2. Structure:
   - You must still return a list of dictionaries with EXACTLY these keys: `date`, `details`, `debit`, `credit`, `balance`, `confidence`.
   - `debit` and `credit` cannot BOTH be non-None in the same transaction. Set the empty one to `None`.
3. Reliability:
   - Wrap parsing logic in `try/except` blocks so one bad row doesn't break everything.
   - Ignore header/footer lines explicitly, but don't accidentally ignore valid rows with words like "Date" or "Balance" in the narration.
4. Debit vs Credit Determination (CRITICAL — Read this carefully):
   - In extracted PDF text, EACH TRANSACTION LINE has exactly 2 monetary values at the end: the AMOUNT and the CLOSING BALANCE.
   - The Withdrawal and Deposit columns from the PDF merge into a single Amount because one is always blank.
   - DO NOT use separate optional regex groups for Withdrawal and Deposit — this ALWAYS fails because regex greedily assigns the only number to whichever group comes first.
   - CORRECT APPROACH: Use `re.findall(r'[\d,]+\.\d{2}', line)` to get all numbers. The last number is Balance, second-to-last is the Amount.
   - Then use a running `previous_balance` variable:
     * If `current_balance > previous_balance`, the Amount is a CREDIT (deposit).
     * If `current_balance < previous_balance`, the Amount is a DEBIT (withdrawal).
     * Update `previous_balance = current_balance` after each transaction.
   - Initialize `previous_balance` from the Opening Balance found in the header, OR from the statement summary line.
   - If the statement DOES NOT have a running balance column, look for literal indicators (like 'CR', 'DR', '+', '-') or the column header to determine debit vs credit.
5. Multi-line Narrations (IMPORTANT):
   - Many PDF text extractions split transaction narrations across multiple lines. The first line starts with a date, and subsequent lines without a date prefix are continuation lines that should be APPENDED to the previous transaction's `details` field.
   - Do NOT treat continuation lines as new transactions.

MANDATORY OUTPUT RULES:
1. Return EXACTLY and ONLY one Python function.
2. The function signature MUST BE EXACTLY: `def extract_transactions(text: str) -> list:`
3. ALL imports MUST be inside the function body. NO top-level code.
4. Write ZERO comments. Every single line MUST be executable Python code. No inline comments (#), no docstrings, no strategy explanations, no planning blocks. Comments waste output tokens and cause truncation.
5. DO NOT wrap the code in markdown (No ```python blocks). Just output the raw text of the python function.
6. The function MUST return the `transactions` list. The VERY LAST LINE must be: `    return transactions`
7. Be CONCISE. Prefer short variable names and compact logic. Do NOT repeat yourself. Avoid redundant checks.

REWRITE THE CODE NOW TO FIX THE MISMATCHES:
"""
    return prompt

def generate_improved_code(
    current_code: str,
    code_transactions: list,
    llm_transactions: list,
    reconciliation: dict,
    remarks: dict,
    pdf_text: str,
    override_patterns: list = [],
    retry_count: int = 0,
    error_message: str = None
) -> str:
    """Call the LLM to generate improved extraction code with syntax validation."""

    prompt = build_improvement_prompt(
        current_code=current_code,
        code_transactions=code_transactions,
        llm_transactions=llm_transactions,
        reconciliation=reconciliation,
        remarks=remarks,
        pdf_text=pdf_text,
        override_patterns=override_patterns,
    )

    if error_message:
        prompt += f"\n\nYOUR PREVIOUS OUTPUT FAILED WITH A PYTHON SYNTAX ERROR:\n{error_message}\nDO NOT MAKE THIS MISTAKE AGAIN. REMOVE ALL STRATEGY COMMENTS AND ONLY OUTPUT VALID EXECUTABLE PYTHON CODE.\n"

    model = genai.GenerativeModel(MODEL_NAME)

    # Disable safety filters
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    print(f"\n====================== PREPARING LLM PROMPT (Size: {len(prompt)}) ======================")

    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.3, # Increased from 0.1 to allow more creative fixes
                "max_output_tokens": 65536
            },
            safety_settings=safety_settings
        )
        content = response.text.strip()
        print(f"\n====================== RAW LLM RESPONSE ======================\n{content[:1000]}...\n============================================================")
        
    except Exception as e:
        print(f"DEBUG: LLM Generation failed: {e}")
        return current_code

    print(f"DEBUG: LLM Raw response length: {len(content)}")

    # Cleanup markdown explicitly by finding the longest python block
    if "```" in content:
        blocks = []
        parts = content.split("```")
        for i in range(1, len(parts), 2):  # Every odd index is inside a markdown fence
            blocks.append(parts[i].strip())
        
        # Pick the largest block (most likely the actual code, not a small strategy block)
        if blocks:
            best_block = max(blocks, key=len)
            if best_block.lower().startswith("python"):
                best_block = best_block[6:].strip()
            content = best_block
    elif content.lower().startswith("python"):
        content = content[6:].strip()

    print(f"DEBUG: Cleaned response length: {len(content)}")

    # --- Truncation Detection ---
    # If the code doesn't have a return statement, the LLM output was likely cut off
    has_return = ("return transactions" in content or "return []" in content)
    if not has_return:
        print(f"DEBUG: TRUNCATION DETECTED — no 'return transactions' found in output. Retrying...")
        if retry_count < 2:
            return generate_improved_code(
                current_code, code_transactions, llm_transactions,
                reconciliation, remarks, pdf_text, override_patterns,
                retry_count + 1,
                error_message="YOUR OUTPUT WAS TRUNCATED. The function is missing 'return transactions' at the end. Write SHORTER, MORE CONCISE code with fewer comments. You MUST end with 'return transactions'."
            )

    # --- Syntax Validation ---
    try:
        tree = ast.parse(content)
        has_func = any(isinstance(node, ast.FunctionDef) and node.name == 'extract_transactions' for node in tree.body)
        if not has_func:
            raise SyntaxError("Function 'extract_transactions' not found in AST.")
        return content
    except SyntaxError as e:
        if retry_count < 2:
            print(f"DEBUG: SyntaxError: {e}. Retrying...")
            return generate_improved_code(
                current_code, code_transactions, llm_transactions,
                reconciliation, remarks, pdf_text, override_patterns,
                retry_count + 1,
                error_message=str(e)
            )
        return content


def build_override_improvement_prompt(
    current_code: str,
    override_patterns: list,
    code_transactions: list,
    llm_transactions: list,
    pdf_text: str,
) -> str:
    """
    Build a prompt for code improvement based on accumulated override patterns.
    
    override_patterns is a list of dicts like:
      {
        "field_name": "debit",
        "ai_value": "1500.00",
        "user_value": "None",
        "occurrences": 3,
        "example_documents": ["doc1.pdf", "doc2.pdf"],
        "example_details": "NEFT TRANSFER..."
      }
    """

    # Build pattern analysis section
    pattern_lines = []
    for i, p in enumerate(override_patterns, 1):
        line = (
            f"PATTERN {i} (occurred {p.get('occurrences', 1)} time(s)):\n"
            f"  Field: {p['field_name']}\n"
            f"  Code extracted: {p.get('ai_value', 'N/A')}\n"
            f"  Correct value:  {p.get('user_value', 'N/A')}\n"
        )
        if p.get('example_details'):
            line += f"  Example transaction: {p['example_details']}\n"
        if p.get('example_documents'):
            line += f"  Seen in documents: {', '.join(p['example_documents'][:3])}\n"
        pattern_lines.append(line)

    patterns_block = "\n".join(pattern_lines) if pattern_lines else "No correction patterns found."

    prompt = f"""Update the following Python extraction function based on FORMAT-WIDE CORRECTION PATTERNS.

CURRENT FUNCTION:
{current_code}

FORMAT PATTERNS (Systematic errors to fix):
{patterns_block}

FULL EXTRACTED PDF TEXT (Context):
{pdf_text}

MANDATORY OUTPUT RULES:
1. Return ONLY the COMPLETE updated Python function.
2. Start with: def extract_transactions(text: str) -> list:
3. Every transaction in the list MUST be a dictionary with these EXACT keys:
   {{ "date": str, "details": str, "debit": float or None, "credit": float or None, "balance": float or None, "confidence": float }}
4. Logic must handle these patterns GENERICALLY for all documents of this format.
5. Include 'import re' and 'from datetime import datetime' inside the function.
6. NO preamble, NO explanations.
7. CRITICAL: The VERY LAST LINE of your response must be: '    return transactions'

UPDATE THE CODE NOW:
"""
    return prompt


def build_positive_reinforcement_prompt(
    current_code: str,
    code_transactions: list,
    pdf_text: str,
) -> str:
    """Build a prompt for code optimization when current results are correct."""
    
    prompt = f"""Optimize and refactor the following Python extraction function. 
The user has verified this logic matches the reference truth perfectly for this document.

CURRENT GOLDEN FUNCTION:
{current_code}

SAMPLE VERIFIED OUTPUT:
{json.dumps(code_transactions[:10], indent=2)}

FULL EXTRACTED PDF TEXT (Context):
{pdf_text}

INSTRUCTIONS:
1. Return ONLY the COMPLETE updated Python function.
2. Optimize for readability, efficiency, and robustness against spacing variations.
3. Ensure it handle multi-line descriptions reliably.
4. NO preamble, NO explanation, NO chat.
5. Function must start with 'def extract_transactions(text: str) -> list:'

REFINE THE GOLDEN CODE NOW:
"""
    return prompt


def generate_override_driven_improvement(
    current_code: str,
    override_patterns: list,
    code_transactions: list,
    llm_transactions: list,
    pdf_text: str,
) -> str:
    """Call the LLM to generate improved extraction code based on override patterns."""

    if not override_patterns:
        # Case: "Set Code as Truth" - Use reinforcement learning
        prompt = build_positive_reinforcement_prompt(
            current_code=current_code,
            code_transactions=code_transactions,
            pdf_text=pdf_text
        )
    else:
        # Case: "Manual Overrides" - Use correction learning
        prompt = build_override_improvement_prompt(
            current_code=current_code,
            override_patterns=override_patterns,
            code_transactions=code_transactions,
            llm_transactions=llm_transactions,
            pdf_text=pdf_text,
        )

    model = genai.GenerativeModel(MODEL_NAME)

    response = model.generate_content(
        prompt,
        generation_config={"temperature": 0}
    )

    content = response.text.strip()

    # Strip markdown fences if the LLM added them
    if "```" in content:
        parts = content.split("```")
        content = parts[1] if len(parts) > 1 else parts[0]
    content = content.strip()
    if content.lower().startswith("python"):
        content = content[6:].strip()

    return content
