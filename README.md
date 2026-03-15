# LEDGER AI - QC Panel Documentation

## Overview
The Quality Control (QC) Panel is the core engine within Ledger AI designed to automatically and manually evaluate the accuracy of data extracted from financial documents (like bank statements). It focuses on comparing the output from two different extraction methods:
1. **LLM Extraction Baseline:** The raw data extracted by the Large Language Model.
2. **Generated Code Extraction:** The data extracted using the Python parsing logic that the LLM iteratively codes and refines.

By comparing these two sources, the QC panel highlights discrepancies, enables user corrections, and feeds context back to the LLM to improve its code generation capabilities—creating an auto-improving data extraction loop.

---

## Key Features & Workflow

### 1. Dual Extraction Comparison
The QC Panel presents a side-by-side or combined view of transactions extracted via the Baseline LLM vs. the Generated Python Code. 
When differences are detected (e.g., missing transactions, wrong dates, incorrect amounts), the UI flags them so a human reviewer can step in.

### 2. Accuracy Scoring
An accuracy score is calculated based on how closely the Code Extraction matches the LLM Baseline. 
- The system is extremely strict: typically, a **99% or 100% accuracy** score is required before code is considered stable.
- If the score falls below the threshold, the code is flagged for improvement.

### 3. Dynamic Code Improvement
When a discrepancy occurs, the user can provide **QC Remarks** (e.g., "The code is missing the closing balance transaction" or "Date format is DD/MM/YYYY").
- The system packages the generated code, the LLM baseline data, the current code output, and the user's remarks.
- This package is sent back to the LLM to dynamically generate **improved Python code**. 

### 4. Overriding the Source of Truth
Neither the LLM nor the Code is strictly treated as the absolute "Source of Truth," as both can make mistakes.
- **Override LLM Baseline:** If the Python code correctly extracted the data but the LLM hallucinated or missed rows, the user can click "Override LLM Baseline." This replaces the flawed LLM baseline with the accurate code output, boosting the accuracy score to 100% and stabilizing the parser.

### 5. Saving the Parser Code
- **Save Code:** Once the code achieves the required accuracy threshold, the user can save the code. This parser is then locked in for this specific bank/statement type.
- **Force Save Code:** In edge cases where the core logic is correct but minor discrepancies persist, administrative users have the option to force-save the current iteration of the code.

### 6. Document Status & Prevention of Re-QC
Once a document is successfully processed and approved through the QC panel, its status is updated to **`REVIEWED`**. 
The system's background `random_qc_service` is explicitly configured to exclude `REVIEWED` documents, ensuring that already-processed documents are not repeatedly pulled back into the QC queue, saving processing power and API quotas.

---

## The Feedback Loop

1. **Upload:** Document is uploaded and identified (Bank Name, Password status).
2. **Baseline:** The LLM attempts a zero-shot extraction (Baseline).
3. **First Pass Code:** The LLM writes a Python script to parse the PDF.
4. **Execution:** The Python script runs against the PDF.
5. **QC Comparison:** The system compares the Baseline vs. Script Output.
6. **Human Intervention:** The reviewer assesses discrepancies via the QC Panel.
7. **Refinement:** The user adds remarks -> The LLM refines the code -> The script runs again.
8. **Finalization:** Accuracy reaches 100% (or LLM Baseline is successfully overridden) -> Code is Saved -> Document marked as `REVIEWED`.

---

## Best Practices for Reviewers
- Always verify the PDF visually if the LLM and Code are in total disagreement.
- Write specific, targeted QC Remarks for the LLM. Example: "Ignore footer text on pages 3 and 4" rather than "Code is wrong."
- Use "Override LLM Baseline" *only* when you are absolutely certain the Python script's output perfectly matches the original PDF.
