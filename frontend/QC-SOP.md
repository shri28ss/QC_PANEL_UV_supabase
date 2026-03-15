QC Detailed SOP: Accuracy of Transaction Extraction Parser
This document defines a step-by-step Quality Control (QC) procedure to validate and improve the accuracy of the transaction extraction parser (Code Parser + LLM Parser + OCR if applicable).
This SOP ensures:
•	No missing transactions
•	No incorrect values
•	No formatting distortion
•	No duplication
•	High structural accuracy
•	Continuous parser improvement
________________________________________
1. Objective
To verify that all transactions in the source document (PDF/Statement) are accurately extracted into structured format without loss, distortion, or misinterpretation.
________________________________________
2. Pre-QC Preparation
Before starting QC:
1.	Open original PDF statement.
2.	Open extracted transaction table (system output).
3.	Enable:
o	PDF Preview Panel
o	Code Parser Output
o	LLM Parser Output (if applicable)
4.	Ensure:
o	Same date range selected
o	Same account
o	Same page count
________________________________________
3. Step-by-Step QC Validation Process
________________________________________
STEP 1: Validate Document Integrity
Checklist:
•	Correct document uploaded?
•	Correct account identified?
•	Correct date range?
•	All pages loaded?
•	Password-protected documents handled correctly?
Action:
If mismatch → mark as Document Mapping Error
________________________________________
STEP 2: Transaction Count Verification
Procedure:
1.	Count transactions in PDF manually (or visually scan).
2.	Count transactions in extracted table.
3.	Compare both numbers.
Acceptable Result:
Counts must match 100%.
If mismatch:
Classify error:
•	Missing transactions
•	Duplicate transactions
•	Partial extraction
•	Page skip error
Mark as:
•	Count Mismatch Error
________________________________________
STEP 3: Row-by-Row Field Validation
For each transaction, verify:
Field	QC Check
Date	Correct format, correct day/month
Description	Complete text, no cut lines
Debit	Correct amount
Credit	Correct amount
Balance	Correct (if available)
Sign	Debit not extracted as credit
Decimal	Proper formatting
Comma separation	Correct numeric parsing
________________________________________
Common Errors to Look For:
•	Missing decimal (.00 missing)
•	Comma misplacement (1,00,000 → 100000)
•	Negative sign lost
•	Debit/Credit swapped
•	Two transactions merged
•	One transaction split into two
•	Description truncated
•	Multi-line descriptions broken
•	Date misread (01/02 vs 02/01 confusion)
•	Balance column shifted
________________________________________
STEP 4: Multi-Line Description Validation
Many banks use multi-line descriptions.
QC must:
•	Confirm full narration captured
•	Ensure next row is not treated as new transaction
•	Verify no unwanted newline splitting
If error found:
Classify as:
•	Multi-line Parsing Error
________________________________________
STEP 5: Transaction Order Validation
Check:
•	Is chronological order maintained?
•	Are transactions sorted correctly?
•	Any missing middle record?
If order mismatch:
•	Flag as Sorting Logic Error
________________________________________
STEP 6: Running Balance Validation (If Available)
Procedure:
1.	Take first transaction.
2.	Manually calculate:
Previous Balance + Credit - Debit
3.	Compare with extracted balance.
If mismatch:
•	Sign error
•	Missing transaction
•	Duplicate entry
•	Decimal parsing error
Flag as:
•	Balance Computation Error
________________________________________
STEP 7: Page Boundary Validation
Check:
•	Transactions at page breaks
•	Last transaction of page 1
•	First transaction of page 2
Often parser misses:
•	Bottom row
•	Header repeated rows
•	Table continuation lines
Flag as:
•	Page Break Extraction Error
________________________________________
STEP 8: Header/Footer Filtering Validation
Ensure parser correctly ignores:
•	Page numbers
•	Totals
•	Summary rows
•	Opening/Closing balance lines
•	Notes section
•	Bank disclaimers
If header extracted as transaction:
•	Flag as Noise Extraction Error
________________________________________
STEP 9: Special Cases Validation
QC must test for:
•	Refund transactions
•	Charge reversals
•	ATM withdrawals
•	POS transactions
•	IMPS/NEFT/UPI formats
•	Foreign currency transactions
•	CR/DR indicators
•	Charges without balance column
•	Statements without explicit debit/credit columns
Flag issues accordingly.
________________________________________
STEP 10: Compare Code Parser vs LLM Parser
If both available:
Create 3-column comparison:
| Field | Code Output | LLM Output |
Check:
•	Which parser missed rows?
•	Which parser misread values?
•	Which parser handled multiline better?
Mark:
•	Code superior
•	LLM superior
•	Both incorrect
________________________________________
4. Error Classification Framework
Every error must be tagged:
1.	Count Mismatch
2.	Multi-line Parsing
3.	Date Format Error
4.	Amount Parsing Error
5.	Sign Misinterpretation
6.	Balance Miscalculation
7.	Duplicate Extraction
8.	Page Boundary Error
9.	Noise Extraction
10.	OCR Misread
11.	Encoding Error
12.	Sorting Logic Error
No generic error tags allowed.
________________________________________
5. Root Cause Identification
After identifying error:
Ask:
•	Is this a regex issue?
•	Is this a table detection issue?
•	Is this OCR problem?
•	Is this pattern mismatch?
•	Is this new bank format?
•	Is this encoding issue?
Document root cause.
________________________________________
6. AI-Assisted Correction Workflow
If parser fails:
1.	Provide:
o	Original PDF snippet
o	Extracted output
o	Corrected version
2.	Ask LLM:
o	Why mismatch happened?
o	Suggest code improvement
3.	Review suggested code
4.	Rerun extraction
5.	Compare new output
6.	Approve or reject changes
________________________________________
7. Accuracy Measurement Formula
Transaction Count Accuracy:
(Extracted Transactions / Actual Transactions) × 100
Field Accuracy:
Correct Fields / Total Fields × 100
Overall Extraction Accuracy:
(Count Accuracy + Field Accuracy) / 2
Target:
•	Count Accuracy = 100%
•	Field Accuracy ≥ 98%
•	Overall ≥ 99%

8. Documentation Requirement
QC must log:
•	Document ID
•	Parser version
•	Error type
•	Screenshot reference
•	Corrected data
•	Suggested fix
•	Final decision
•	Approval timestamp
________________________________________
9. Release Approval Criteria
Parser can move to production only if:
•	100% transaction count accuracy
•	No structural extraction failure
•	Multi-line parsing verified
•	Page break validated
•	Balance validation passed
•	QC sign-off recorded
________________________________________
10. Continuous Improvement Loop
1.	Detect error
2.	Classify error
3.	Identify root cause
4.	Fix logic
5.	Re-test
6.	Re-measure accuracy
7.	Approve
8.	Deploy
________________________________________
Final Objective
QC must ensure:
•	Zero missing transactions
•	Zero duplicates
•	No amount distortion
•	No debit/credit confusion
•	No multiline breaks
•	No page loss
Only after this foundation is strong can categorization accuracy be trusted.

