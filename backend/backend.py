import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from db.connection import get_connection, get_cursor
from fastapi.responses import FileResponse, JSONResponse
import uvicorn
import pikepdf
import tempfile
import os
import logging
from typing import Dict, Any, List, Optional, Union

# Configure logging so scheduler & QC logs appear in terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
#for cron job
from contextlib import asynccontextmanager
from services.scheduler_service import start_scheduler, stop_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # This runs when the server starts
    start_scheduler()
    yield
    # This runs when the server stops
    stop_scheduler()

app = FastAPI(lifespan=lifespan)

# Enable CORS for the local React development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_document_password(document_id: int):
    """Fetch the stored password for a document from the document_password table."""
    conn = get_connection()
    cursor = get_cursor(conn)
    cursor.execute("""
        SELECT encrypted_password
        FROM document_password
        WHERE document_id = %s
    """, (document_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result[0] if result else None

@app.get("/api/review-documents")
def get_under_review_documents():
    conn = get_connection()
    cursor = get_cursor(conn)
    
    # Query to join documents, statement_categories and latest QC results
    query = """
        SELECT 
            sc.statement_id,
            d.document_id,
            d.user_id,
            sc.statement_type,
            sc.institution_name,
            sc.status as format_status,
            d.status as doc_status,
            d.transaction_parsed_type,
            (SELECT COUNT(*) FROM random_qc_results qr WHERE qr.document_id = d.document_id AND qr.qc_status = 'FLAGGED') as is_auto_flagged,
            (SELECT accuracy FROM random_qc_results qr WHERE qr.document_id = d.document_id ORDER BY created_at DESC LIMIT 1) as last_qc_accuracy
        FROM documents d
        JOIN statement_categories sc ON d.statement_id = sc.statement_id
        WHERE sc.status = 'EXPERIMENTAL'
    """
    
    cursor.execute(query)
    rows = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return rows

@app.get("/api/document-logic/{document_id}")
def get_document_logic(document_id: int):
    from services.reconciliation_service import reconcile_transactions
    import json

    conn = get_connection()
    cursor = get_cursor(conn)
    
    # 1. Get extraction logic
    query_logic = """
        SELECT sc.extraction_logic, sc.institution_name, d.file_name
        FROM documents d
        JOIN statement_categories sc ON d.statement_id = sc.statement_id
        WHERE d.document_id = %s
    """
    cursor.execute(query_logic, (document_id,))
    logic_row = cursor.fetchone()
    
    # 2. Get CODE transactions
    cursor.execute("SELECT transaction_json FROM ai_transactions_staging WHERE document_id = %s AND parser_type = 'CODE' ORDER BY created_at DESC LIMIT 1", (document_id,))
    code_row = cursor.fetchone()
    
    # 3. Get LLM transactions
    cursor.execute("SELECT transaction_json FROM ai_transactions_staging WHERE document_id = %s AND parser_type = 'LLM' ORDER BY created_at DESC LIMIT 1", (document_id,))
    llm_row = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    code_txns = json.loads(code_row["transaction_json"]) if code_row and code_row["transaction_json"] else []
    llm_txns = json.loads(llm_row["transaction_json"]) if llm_row and llm_row["transaction_json"] else []

    reconciliation = reconcile_transactions(code_txns, llm_txns)
    
    return {
        "extraction_logic": logic_row["extraction_logic"] if logic_row else "",
        "institution_name": logic_row["institution_name"] if logic_row else "Unknown",
        "file_name": logic_row["file_name"] if logic_row else "document.pdf",
        "code_transactions": code_row["transaction_json"] if code_row else "[]",
        "llm_transactions": llm_row["transaction_json"] if llm_row else "[]",
        "reconciliation": reconciliation
    }

@app.get("/api/document-pdf/{document_id}")
def get_document_pdf(document_id: int):
    conn = get_connection()
    cursor = get_cursor(conn)
    cursor.execute("SELECT file_path, file_name FROM documents WHERE document_id = %s", (document_id,))
    doc = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not doc or not doc['file_path'] or not os.path.exists(doc['file_path']):
        missing_path = doc['file_path'] if doc and doc['file_path'] else "unknown"
        return JSONResponse(
            status_code=404,
            content={"error": f"PDF file not found on disk: {missing_path}"}
        )
    
    file_path = doc['file_path']
    # Guard: file_name might accidentally have a full path stored — use only the basename
    file_name = os.path.basename(doc['file_name']) if doc['file_name'] else os.path.basename(file_path)
    
    # Try to get the password from document_password table
    password = _get_document_password(document_id)
    
    if password:
        # Decrypt the PDF and serve the decrypted version
        try:
            pdf = pikepdf.open(file_path, password=password)
            # Save decrypted PDF to a temp file
            temp_dir = tempfile.gettempdir()
            decrypted_path = os.path.join(temp_dir, f"decrypted_{document_id}_{file_name}")
            pdf.save(decrypted_path)
            pdf.close()
            return FileResponse(
                path=decrypted_path,
                media_type='application/pdf',
                content_disposition_type='inline'
            )
        except Exception as e:
            print(f"Error decrypting PDF {document_id}: {e}")
            # Fallback: serve original file
            return FileResponse(
                path=file_path,
                media_type='application/pdf',
                content_disposition_type='inline'
            )
    
    return FileResponse(
        path=file_path,
        media_type='application/pdf',
        content_disposition_type='inline'
    )

# ======================================================================
# CODE IMPROVEMENT & RE-RUN ENDPOINTS
# ======================================================================
from pydantic import BaseModel
from typing import Dict, List, Any, Optional

class ImproveCodeRequest(BaseModel):
    reconciliation: Dict[str, Any]
    remarks: Dict[str, str] = {}
    accepted_ids: List[str] = []

class RunImprovedCodeRequest(BaseModel):
    improved_code: str

@app.post("/api/improve-code/{document_id}")
def improve_code(document_id: int, req: ImproveCodeRequest):
    from services.code_improvement_service import generate_improved_code
    from services.pdf_service import extract_full_text
    import json

    conn = get_connection()
    cursor = get_cursor(conn)

    # 1. Initialize variables
    current_code = ""
    current_statement_id = None

    # 2. Get current extraction logic and statement_id
    cursor.execute("""
        SELECT sc.extraction_logic, d.statement_id
        FROM documents d
        JOIN statement_categories sc ON d.statement_id = sc.statement_id
        WHERE d.document_id = %s
    """, (document_id,))
    logic_row = cursor.fetchone()
    
    if logic_row:
        current_code = logic_row.get("extraction_logic", "")
        current_statement_id = logic_row.get("statement_id")

    # Get CODE transactions
    cursor.execute("SELECT transaction_json FROM ai_transactions_staging WHERE document_id = %s AND parser_type = 'CODE' ORDER BY created_at DESC LIMIT 1", (document_id,))
    code_row = cursor.fetchone()
    code_txns = json.loads(code_row["transaction_json"]) if code_row and code_row["transaction_json"] else []

    # Get LLM transactions
    cursor.execute("SELECT transaction_json FROM ai_transactions_staging WHERE document_id = %s AND parser_type = 'LLM' ORDER BY created_at DESC LIMIT 1", (document_id,))
    llm_row = cursor.fetchone()
    llm_txns = json.loads(llm_row["transaction_json"]) if llm_row and llm_row["transaction_json"] else []

    # Get PDF text
    cursor.execute("SELECT extracted_text FROM document_text_extractions WHERE document_id = %s ORDER BY created_at DESC LIMIT 1", (document_id,))
    text_row = cursor.fetchone()
    pdf_text = text_row["extracted_text"] if text_row else ""

    cursor.close()
    conn.close()

    # If no PDF text, try extracting from file
    if not pdf_text:
        conn2 = get_connection()
        cursor2 = get_cursor(conn2)
        cursor2.execute("SELECT file_path FROM documents WHERE document_id = %s", (document_id,))
        doc = cursor2.fetchone()
        cursor2.close()
        conn2.close()
        if doc and doc["file_path"] and os.path.exists(doc["file_path"]):
            password = _get_document_password(document_id)
            pdf_text = extract_full_text(doc["file_path"], password)

    # --- Fetch systemic override patterns for this format ---
    conn_p = get_connection()
    cursor_p = get_cursor(conn_p)
    cursor_p.execute("""
        SELECT 
            o.field_name,
            o.ai_value,
            o.user_value,
            COUNT(*) as occurrences
        FROM transaction_overrides o
        JOIN ai_transactions_staging s ON o.staging_transaction_id = s.staging_transaction_id
        JOIN documents d ON s.document_id = d.document_id
        WHERE d.statement_id = %s
        GROUP BY o.field_name, o.ai_value, o.user_value
        ORDER BY occurrences DESC
        LIMIT 20
    """, (current_statement_id,))
    override_patterns = cursor_p.fetchall()
    cursor_p.close()
    conn_p.close()

    try:
        improved_code = generate_improved_code(
            current_code=current_code,
            code_transactions=code_txns,
            llm_transactions=llm_txns,
            reconciliation=req.reconciliation,
            remarks=req.remarks,
            pdf_text=pdf_text,
            override_patterns=override_patterns,
        )
    except Exception as e:
        error_msg = str(e)
        print(f"ERROR in improve_code endpoint: {error_msg}")
        if "quota" in error_msg.lower() or "rate" in error_msg.lower() or "resource" in error_msg.lower():
            return {"error": f"Gemini API quota exceeded. Please wait a minute and try again. Details: {error_msg}"}
        return {"error": f"Failed to generate improved code: {error_msg}"}

    return {
        "original_code": current_code,
        "improved_code": improved_code,
    }


@app.post("/api/run-improved-code/{document_id}")
def run_improved_code(document_id: int, req: RunImprovedCodeRequest):
    from services.extraction_service import extract_transactions_using_logic
    from services.reconciliation_service import reconcile_transactions
    from services.pdf_service import extract_full_text
    import json

    conn = get_connection()
    cursor = get_cursor(conn)

    # Get PDF text
    cursor.execute("SELECT extracted_text FROM document_text_extractions WHERE document_id = %s ORDER BY created_at DESC LIMIT 1", (document_id,))
    text_row = cursor.fetchone()
    pdf_text = text_row["extracted_text"] if text_row else ""

    # Get LLM transactions for comparison
    cursor.execute("SELECT transaction_json FROM ai_transactions_staging WHERE document_id = %s AND parser_type = 'LLM' ORDER BY created_at DESC LIMIT 1", (document_id,))
    llm_row = cursor.fetchone()
    llm_txns = json.loads(llm_row["transaction_json"]) if llm_row and llm_row["transaction_json"] else []

    cursor.close()
    conn.close()

    # If no PDF text, try extracting from file
    if not pdf_text:
        conn2 = get_connection()
        cursor2 = get_cursor(conn2)
        cursor2.execute("SELECT file_path FROM documents WHERE document_id = %s", (document_id,))
        doc = cursor2.fetchone()
        cursor2.close()
        conn2.close()
        if doc and doc["file_path"] and os.path.exists(doc["file_path"]):
            password = _get_document_password(document_id)
            pdf_text = extract_full_text(doc["file_path"], password)

    # Execute the improved code
    try:
        new_transactions = extract_transactions_using_logic(pdf_text, req.improved_code)
    except Exception as e:
        return {"error": str(e), "new_transactions": [], "reconciliation": None}

    # Reconcile new code transactions against LLM
    reconciliation = reconcile_transactions(new_transactions, llm_txns)

    return {
        "new_transactions": new_transactions,
        "reconciliation": reconciliation,
        "transaction_count": len(new_transactions),
    }


class SaveImprovedCodeRequest(BaseModel):
    improved_code: str
    overwrite_llm: bool = False
    accuracy: Optional[float] = None

@app.post("/api/save-improved-code/{document_id}")
def save_improved_code(document_id: int, req: SaveImprovedCodeRequest):
    from services.extraction_service import extract_transactions_using_logic
    from services.pdf_service import extract_full_text
    import json

    conn = get_connection()
    cursor = get_cursor(conn)

    # Find the statement_id for this document
    cursor.execute("""
        SELECT d.statement_id
        FROM documents d
        WHERE d.document_id = %s
    """, (document_id,))
    doc = cursor.fetchone()

    if not doc or not doc["statement_id"]:
        cursor.close()
        conn.close()
        return {"error": "No statement linked to this document"}

    statement_id = doc["statement_id"]

    # Update extraction_logic, set format status to ACTIVE, and update accuracy
    if req.accuracy is not None:
        cursor.execute("""
            UPDATE statement_categories
            SET extraction_logic = %s, status = 'ACTIVE', success_rate = %s
            WHERE statement_id = %s
        """, (req.improved_code, req.accuracy, statement_id))
    else:
        cursor.execute("""
            UPDATE statement_categories
            SET extraction_logic = %s, status = 'ACTIVE'
            WHERE statement_id = %s
        """, (req.improved_code, statement_id))

    # Also clear any FLAGGED QC results for this format since we just fixed the logic
    # Deleting them ensures Random QC will test these documents again in its next run
    cursor.execute("""
        DELETE FROM random_qc_results 
        WHERE statement_id = %s AND qc_status = 'FLAGGED'
    """, (statement_id,))

    conn.commit()
    cursor.close()
    conn.close()

    # ---- Re-run the improved code and update stored CODE transactions ----
    try:
        # Get PDF text
        conn2 = get_connection()
        cursor2 = get_cursor(conn2)
        cursor2.execute("""
            SELECT extracted_text FROM document_text_extractions
            WHERE document_id = %s ORDER BY created_at DESC LIMIT 1
        """, (document_id,))
        text_row = cursor2.fetchone()
        pdf_text = text_row["extracted_text"] if text_row else ""

        # If no cached text, extract from file
        if not pdf_text:
            cursor2.execute("SELECT file_path FROM documents WHERE document_id = %s", (document_id,))
            doc_row = cursor2.fetchone()
            cursor2.close()
            conn2.close()
            if doc_row and doc_row["file_path"] and os.path.exists(doc_row["file_path"]):
                password = _get_document_password(document_id)
                pdf_text = extract_full_text(doc_row["file_path"], password)
        else:
            cursor2.close()
            conn2.close()

        if pdf_text:
            # Run the improved code to get new transactions
            new_transactions = extract_transactions_using_logic(pdf_text, req.improved_code)

            if new_transactions:
                # Update the CODE transactions in ai_transactions_staging
                conn3 = get_connection()
                cursor3 = get_cursor(conn3)
                # Get user_id
                cursor3.execute("SELECT user_id FROM documents WHERE document_id = %s", (document_id,))
                uid_row = cursor3.fetchone()
                uid = uid_row["user_id"] if uid_row else 1
                cursor3.execute("""
                    INSERT INTO ai_transactions_staging
                    (document_id, user_id, parser_type, transaction_json, overall_confidence)
                    VALUES (%s, %s, 'CODE', %s, %s)
                """, (document_id, uid, json.dumps(new_transactions), 1.0))

                if req.overwrite_llm:
                    cursor3.execute("""
                        INSERT INTO ai_transactions_staging
                        (document_id, user_id, parser_type, transaction_json, overall_confidence)
                        VALUES (%s, %s, 'LLM', %s, %s)
                    """, (document_id, uid, json.dumps(new_transactions), 1.0))

                conn3.commit()
                cursor3.close()
                conn3.close()

                return {
                    "success": True,
                    "message": f"Improved code saved, status set to ACTIVE, and {len(new_transactions)} CODE transactions updated."
                }

    except Exception as e:
        print(f"Warning: Code saved but failed to re-run extraction: {e}")

    return {"success": True, "message": "Improved code saved and format status set to ACTIVE"}


# ======================================================================
# OVERRIDE & IMPROVE CODE
# ======================================================================

@app.post("/api/override-and-improve/{document_id}")
def override_and_improve(document_id: int):
    """
    Smart override that:
    1. Overwrites LLM baseline with CODE transactions (for this document).
    2. Gathers ALL override patterns for the same statement format.
    3. Uses LLM to generate improved extraction code based on those patterns.
    4. Saves the improved code to statement_categories (for ALL docs of this format).
    5. Re-runs the improved code on the current document.
    """
    from services.code_improvement_service import generate_override_driven_improvement
    from services.extraction_service import extract_transactions_using_logic
    from services.reconciliation_service import reconcile_transactions
    from services.pdf_service import extract_full_text
    import json

    conn = get_connection()
    cursor = get_cursor(conn)

    # ── Step 1: Get document info and statement_id ──
    cursor.execute("""
        SELECT d.statement_id, d.user_id, d.file_path,
               sc.extraction_logic, sc.institution_name
        FROM documents d
        JOIN statement_categories sc ON d.statement_id = sc.statement_id
        WHERE d.document_id = %s
    """, (document_id,))
    doc_info = cursor.fetchone()

    if not doc_info or not doc_info["statement_id"]:
        cursor.close()
        conn.close()
        return {"error": "Document or statement category not found."}

    statement_id = doc_info["statement_id"]
    current_code = doc_info["extraction_logic"] or ""
    uid = doc_info["user_id"] or 1

    # ── Step 2: Get CODE transactions & overwrite LLM baseline ──
    cursor.execute("""
        SELECT transaction_json FROM ai_transactions_staging
        WHERE document_id = %s AND parser_type = 'CODE'
        ORDER BY created_at DESC LIMIT 1
    """, (document_id,))
    code_row = cursor.fetchone()

    if not code_row or not code_row["transaction_json"]:
        cursor.close()
        conn.close()
        return {"error": "No CODE transactions found to set as baseline."}

    code_txns = json.loads(code_row["transaction_json"])

    # Insert CODE as new LLM baseline
    cursor.execute("""
        INSERT INTO ai_transactions_staging
        (document_id, user_id, parser_type, transaction_json, overall_confidence)
        VALUES (%s, %s, 'LLM', %s, %s)
    """, (document_id, uid, code_row["transaction_json"], 1.0))
    conn.commit()

    # ── Step 3: Get LLM transactions (the original ones, before override) ──
    cursor.execute("""
        SELECT transaction_json FROM ai_transactions_staging
        WHERE document_id = %s AND parser_type = 'LLM'
        ORDER BY created_at DESC LIMIT 1 OFFSET 1
    """, (document_id,))
    old_llm_row = cursor.fetchone()
    old_llm_txns = json.loads(old_llm_row["transaction_json"]) if old_llm_row and old_llm_row["transaction_json"] else code_txns

    # ── Step 4: Gather ALL override patterns for this statement format ──
    cursor.execute("""
        SELECT 
            o.field_name,
            o.ai_value,
            o.user_value,
            COUNT(*) as occurrences,
            GROUP_CONCAT(DISTINCT d.file_name SEPARATOR ', ') as example_documents
        FROM transaction_overrides o
        JOIN ai_transactions_staging s ON o.staging_transaction_id = s.staging_transaction_id
        JOIN documents d ON s.document_id = d.document_id
        WHERE d.statement_id = %s
        GROUP BY o.field_name, o.ai_value, o.user_value
        ORDER BY occurrences DESC
        LIMIT 30
    """, (statement_id,))
    override_rows = cursor.fetchall()

    override_patterns = []
    for row in override_rows:
        override_patterns.append({
            "field_name": row["field_name"],
            "ai_value": row["ai_value"],
            "user_value": row["user_value"],
            "occurrences": row["occurrences"],
            "example_documents": row["example_documents"].split(", ") if row["example_documents"] else [],
        })

    # ── Step 5: Get PDF text for context ──
    cursor.execute("""
        SELECT extracted_text FROM document_text_extractions
        WHERE document_id = %s ORDER BY created_at DESC LIMIT 1
    """, (document_id,))
    text_row = cursor.fetchone()
    pdf_text = text_row["extracted_text"] if text_row else ""

    cursor.close()
    conn.close()

    # If no cached text, extract from file
    if not pdf_text and doc_info.get("file_path") and os.path.exists(doc_info["file_path"]):
        password = _get_document_password(document_id)
        pdf_text = extract_full_text(doc_info["file_path"], password)

    # ── Step 6: If we have override patterns, generate improved code ──
    improved_code = None
    improvement_error = None

    # Always try to improve if we have code. 
    # If patterns=[], the service will trigger "Reinforcement" (optimization).
    if current_code:
        try:
            improved_code = generate_override_driven_improvement(
                current_code=current_code,
                override_patterns=override_patterns,
                code_transactions=code_txns,
                llm_transactions=old_llm_txns,
                pdf_text=pdf_text,
            )
        except Exception as e:
            improvement_error = str(e)
            print(f"WARNING: Override-driven improvement failed: {e}")

    # ── Step 7: If improved code generated, save it & re-run ──
    new_transactions = None
    new_reconciliation = None

    if improved_code:
        try:
            # Test the improved code first
            new_transactions = extract_transactions_using_logic(pdf_text, improved_code)

            if new_transactions:
                # Reconcile against the (original) LLM to check quality
                new_reconciliation = reconcile_transactions(new_transactions, old_llm_txns)
                print("DEBUG: Improved code generated via override. User must re-run and save manually.")

        except Exception as e:
            improvement_error = f"Code ran but failed: {str(e)}"
            print(f"WARNING: Improved code execution failed: {e}")

    # Build descriptive message
    msg = "LLM baseline overwritten with Code output. "
    if improved_code and not improvement_error:
        if not override_patterns:
            msg += "Since code was correct, the LLM further Optimized & Generalized the logic for all documents."
        else:
            msg += f"Logic Improved using {len(override_patterns)} correction patterns and saved for all documents."
    elif improvement_error:
        msg += f"Improvement attempted but failed: {improvement_error}"
    else:
        msg += "Logic remains unchanged (no improvements suggested)."

    return {
        "success": True,
        "llm_overwritten": True,
        "override_patterns_found": len(override_patterns),
        "code_improved": improved_code is not None and improvement_error is None,
        "improved_code": improved_code,
        "new_transaction_count": len(new_transactions) if new_transactions else None,
        "new_transactions": new_transactions,
        "new_reconciliation": new_reconciliation,
        "improvement_error": improvement_error,
        "message": msg
    }


# Keep the old endpoint for backward compatibility, but redirect to the new one
@app.post("/api/overwrite-llm-baseline/{document_id}")
def overwrite_llm_baseline(document_id: int):
    """Legacy endpoint — now redirects to override-and-improve."""
    return override_and_improve(document_id)



# ======================================================================
# RANDOM QC ENDPOINTS
# ======================================================================

@app.post("/api/run-llm/{document_id}")
def run_llm_extraction(document_id: int):
    """Manually trigger LLM extraction for a document (if no txns found)."""
    from services.pdf_service import extract_full_text
    from services.llm_parser import parse_with_llm
    from services.reconciliation_service import reconcile_transactions
    from services.validation_service import extract_json_from_response
    import json

    conn = get_connection()
    cursor = get_cursor(conn)

    # 1. Get PDF text
    cursor.execute("SELECT extracted_text FROM document_text_extractions WHERE document_id = %s ORDER BY created_at DESC LIMIT 1", (document_id,))
    text_row = cursor.fetchone()
    pdf_text = text_row["extracted_text"] if text_row else ""

    # Get statement_id, file_path, and identifier
    cursor.execute("""
        SELECT d.statement_id, d.file_path, sc.statement_identifier 
        FROM documents d
        JOIN statement_categories sc ON d.statement_id = sc.statement_id
        WHERE d.document_id = %s
    """, (document_id,))
    doc_row = cursor.fetchone()

    if not doc_row:
        cursor.close()
        conn.close()
        return {"error": "Document or statement category not found"}
    
    # Get Code transactions for reconciliation
    cursor.execute("SELECT transaction_json FROM ai_transactions_staging WHERE document_id = %s AND parser_type = 'CODE' ORDER BY created_at DESC LIMIT 1", (document_id,))
    code_row = cursor.fetchone()
    code_txns = json.loads(code_row["transaction_json"]) if code_row and code_row["transaction_json"] else []

    cursor.close()
    conn.close()

    if not pdf_text and doc_row and doc_row["file_path"]:
        password = _get_document_password(document_id)
        pdf_text = extract_full_text(doc_row["file_path"], password)

    if not pdf_text:
        return {"error": "Could not extract PDF text"}

    # 2. Call LLM
    try:
        identifier_json = json.loads(doc_row["statement_identifier"]) if isinstance(doc_row["statement_identifier"], str) else doc_row["statement_identifier"]
        llm_response = parse_with_llm(pdf_text, identifier_json)
        llm_transactions = extract_json_from_response(llm_response)
    except Exception as e:
        return {"error": f"LLM Call failed: {str(e)}"}

    if not llm_transactions:
        return {"error": "LLM returned no transactions"}

    # 3. Save to DB
    conn2 = get_connection()
    cursor2 = get_cursor(conn2)
    # Get user_id
    cursor2.execute("SELECT user_id FROM documents WHERE document_id = %s", (document_id,))
    uid_row = cursor2.fetchone()
    uid = uid_row["user_id"] if uid_row else 1
    cursor2.execute("""
        INSERT INTO ai_transactions_staging (document_id, user_id, parser_type, transaction_json, overall_confidence)
        VALUES (%s, %s, 'LLM', %s, %s)
    """, (document_id, uid, json.dumps(llm_transactions), 0.95))
    conn2.commit()
    cursor2.close()
    conn2.close()

    # 4. Reconcile
    reconciliation = reconcile_transactions(code_txns, llm_transactions)

    return {
        "success": True,
        "llm_transactions": llm_transactions,
        "reconciliation": reconciliation
    }


@app.post("/api/random-qc-trigger")
def trigger_random_qc():
    """Manually trigger a random QC run (for testing)."""
    from services.random_qc_service import run_random_qc
    result = run_random_qc(sample_size=1)
    return result


@app.get("/api/random-qc-results")
def get_random_qc_results():
    """Get all QC results for the dashboard table."""
    import json
    conn = get_connection()
    cursor = get_cursor(conn)
    cursor.execute("""
        SELECT qc_id, document_id, statement_id, file_name, institution_name,
               code_txn_count, llm_txn_count, matched_count,
               unmatched_code_count, unmatched_llm_count, accuracy,
               qc_status, created_at, reviewed_at
        FROM random_qc_results
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


@app.get("/api/random-qc-summary")
def get_random_qc_summary():
    """Get summary cards data for the dashboard."""
    conn = get_connection()
    cursor = get_cursor(conn)
    cursor.execute("""
        SELECT 
            COUNT(*) as total_checked,
            ROUND(AVG(accuracy), 1) as avg_accuracy,
            MIN(accuracy) as lowest_accuracy,
            MAX(accuracy) as highest_accuracy,
            SUM(CASE WHEN qc_status = 'PENDING' THEN 1 ELSE 0 END) as pending_count,
            SUM(CASE WHEN qc_status = 'REVIEWED' THEN 1 ELSE 0 END) as reviewed_count,
            SUM(CASE WHEN qc_status = 'FLAGGED' THEN 1 ELSE 0 END) as flagged_count
        FROM random_qc_results
    """)
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


@app.get("/api/random-qc-detail/{qc_id}")
def get_random_qc_detail(qc_id: int):
    """Get full detail for one QC result (for the detail/view page)."""
    import json
    conn = get_connection()
    cursor = get_cursor(conn)
    cursor.execute("""
        SELECT * FROM random_qc_results WHERE qc_id = %s
    """, (qc_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row:
        return {"error": "QC result not found"}

    # Parse JSON fields
    row["reconciliation_json"] = json.loads(row["reconciliation_json"]) if row["reconciliation_json"] else {}
    row["code_txn_json"] = json.loads(row["code_txn_json"]) if row["code_txn_json"] else []
    row["llm_txn_json"] = json.loads(row["llm_txn_json"]) if row["llm_txn_json"] else []

    return row


@app.post("/api/random-qc-review/{qc_id}")
def submit_qc_review(qc_id: int, review: dict):
    """Submit a QC review (mark as reviewed/flagged, add notes)."""
    conn = get_connection()
    cursor = get_cursor(conn)
    cursor.execute("""
        UPDATE random_qc_results
        SET qc_status = %s,
            reviewer_notes = %s,
            issue_type = %s,
            assigned_to = %s,
            reviewed_at = NOW()
        WHERE qc_id = %s
    """, (
        review.get("qc_status", "REVIEWED"),
        review.get("reviewer_notes", ""),
        review.get("issue_type", ""),
        review.get("assigned_to", ""),
        qc_id
    ))
    conn.commit()
    cursor.close()
    conn.close()
    return {"success": True, "message": f"QC {qc_id} reviewed successfully"}


# ======================================================================
# FREQUENTLY CHANGED TRANSACTIONS ENDPOINTS
# ======================================================================

@app.get("/api/frequent-overrides-summary")
def get_frequent_overrides_summary():
    """Summary of transaction overrides with heat map & bank ranking data."""
    import json as _json
    conn = get_connection()
    cursor = get_cursor(conn)
    
    # Basic totals
    cursor.execute("""
        SELECT 
            COUNT(*) as total_overrides,
            COUNT(DISTINCT o.staging_transaction_id) as total_staging,
            COUNT(DISTINCT s.document_id) as total_documents
        FROM transaction_overrides o
        JOIN ai_transactions_staging s ON o.staging_transaction_id = s.staging_transaction_id
    """)
    totals = cursor.fetchone()

    # Top problem field
    cursor.execute("""
        SELECT field_name, COUNT(*) as field_count 
        FROM transaction_overrides 
        GROUP BY field_name 
        ORDER BY field_count DESC 
        LIMIT 1
    """)
    top_field_row = cursor.fetchone()

    # --- HEAT MAP DATA: count per field ---
    cursor.execute("""
        SELECT field_name, COUNT(*) as cnt
        FROM transaction_overrides
        GROUP BY field_name
        ORDER BY cnt DESC
    """)
    field_heatmap = cursor.fetchall()  # [{field_name, cnt}, ...]

    # --- BANK RANKING: changes per institution ---
    cursor.execute("""
        SELECT sc.institution_name, COUNT(*) as change_count
        FROM transaction_overrides o
        JOIN ai_transactions_staging s ON o.staging_transaction_id = s.staging_transaction_id
        JOIN documents d ON s.document_id = d.document_id
        JOIN statement_categories sc ON d.statement_id = sc.statement_id
        GROUP BY sc.institution_name
        ORDER BY change_count DESC
    """)
    bank_ranking = cursor.fetchall()  # [{institution_name, change_count}, ...]

    cursor.close()
    conn.close()
    
    return {
        "total_overrides": totals["total_overrides"] if totals else 0,
        "total_documents": totals["total_documents"] if totals else 0,
        "top_problem_field": top_field_row["field_name"] if top_field_row else "None",
        "top_problem_count": top_field_row["field_count"] if top_field_row else 0,
        "field_heatmap": field_heatmap or [],
        "bank_ranking": bank_ranking or []
    }

@app.get("/api/frequent-overrides")
def get_frequent_overrides():
    """List documents with overrides, sorted by most changes. Includes before/after transactions."""
    import json
    conn = get_connection()
    cursor = get_cursor(conn)
    
    query = """
        SELECT 
            d.document_id,
            d.file_name,
            sc.institution_name,
            o.override_id,
            o.field_name,
            o.ai_value,
            o.user_value,
            o.overridden_at,
            s.transaction_json
        FROM transaction_overrides o
        JOIN ai_transactions_staging s ON o.staging_transaction_id = s.staging_transaction_id
        JOIN documents d ON s.document_id = d.document_id
        JOIN statement_categories sc ON d.statement_id = sc.statement_id
        ORDER BY d.document_id, o.overridden_at DESC
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    # Dictionary to group overrides by document_id
    docs_map: Dict[int, Dict[str, Any]] = {}

    for row in rows:
        doc_id = row["document_id"]
        
        if doc_id not in docs_map:
            docs_map[doc_id] = {
                "document_id": doc_id,
                "file_name": row["file_name"],
                "institution_name": row["institution_name"] or "Unknown",
                "total_changes": 0,
                "overrides": []
            }
        
        # Parse transaction_json to find the contextual transaction
        txns: list = []
        if isinstance(row["transaction_json"], str):
            try:
                txns = json.loads(row["transaction_json"])
            except Exception:
                pass
        elif isinstance(row["transaction_json"], list):
            txns = row["transaction_json"]
        
        # Try to find the exact original transaction in the array
        original_txn: Optional[Dict[str, Any]] = None
        for t in txns:
            if not isinstance(t, dict):
                continue
            if str(t.get(row["field_name"], "")) == str(row["ai_value"] or ""):
                original_txn = t.copy()  # copy so we don't mutate
                break
        
        if not original_txn:
            # Provide a fallback dict for type safety
            original_txn = {"date": "N/A", "details": "Could not locate original row", "debit": "-", "credit": "-", "balance": "-"}

        # Build the corrected version by applying the user's fix
        corrected_txn: Dict[str, Any] = {**original_txn}
        corrected_txn[str(row["field_name"])] = row["user_value"]

        override_obj = {
            "override_id": row["override_id"],
            "field_name": row["field_name"],
            "ai_value": row["ai_value"],
            "user_value": row["user_value"],
            "overridden_at": row["overridden_at"].isoformat() if row["overridden_at"] else None,
            "original_transaction": original_txn,
            "corrected_transaction": corrected_txn
        }

        doc_data = docs_map[doc_id]
        overrides_list: List[Any] = doc_data["overrides"]
        overrides_list.append(override_obj)
        doc_data["total_changes"] += 1

    # Convert map to list & sort by total_changes descending
    results = list(docs_map.values())
    results.sort(key=lambda x: x["total_changes"], reverse=True)

    return results

@app.post("/api/generate-llm-report")
def generate_llm_report():
    """Generates an LLM prompt improvement report based on frequent overrides."""
    conn = get_connection()
    cursor = get_cursor(conn)
    
    cursor.execute("""
        SELECT field_name, ai_value, user_value, COUNT(*) as occorrences
        FROM transaction_overrides 
        GROUP BY field_name, ai_value, user_value
        ORDER BY occorrences DESC
        LIMIT 20
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        return {
            "success": True,
            "report_text": "Not enough override data to generate a report. Keep reviewing documents!"
        }

    # Format a simple text report
    report_lines = [
        "### 📊 LLM Extraction Improvement Report",
        "Based on recent manual corrections, here are the most frequent AI mistakes:",
        "---"
    ]

    for r in rows:
        report_lines.append(
            f"- **Field `{r['field_name']}`**: AI frequently outputs `{r['ai_value']}`, but humans corrected it to `{r['user_value']}` ({r['occorrences']} times)."
        )

    report_lines.append("---")
    report_lines.append("💡 **Recommendation for Prompt:**")
    top_field = rows[0]['field_name']
    report_lines.append(f"- Add specific rules regarding **{top_field}** extraction to prevent misclassifying `{rows[0]['ai_value']}`.")
    report_lines.append("- Provide examples of correct extraction where this pattern appears.")

    return {
        "success": True,
        "report_text": "\n".join(report_lines)
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
