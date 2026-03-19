
import json
def safe_json_loads(data):
    if isinstance(data, (dict, list)): return data
    if isinstance(data, str):
        try: return safe_json_loads(data)
        except: return None
    return data
#imports
import json
import random
import logging
from db.connection import get_connection, get_cursor
from services.reconciliation_service import reconcile_transactions
from services.llm_parser import parse_with_llm
from services.validation_service import extract_json_from_response
from services.pdf_service import extract_full_text
from services.extraction_service import extract_transactions_using_logic

logger = logging.getLogger(__name__)


def _get_active_documents():
    """Fetch all documents that have an ACTIVE format status and haven't been REVIEWED already."""
    conn = get_connection()
    cursor = get_cursor(conn)
    cursor.execute("""
        SELECT 
            d.document_id,
            d.statement_id,
            d.file_name,
            d.file_path,
            sc.institution_name,
            sc.extraction_logic,
            sc.statement_identifier
        FROM documents d
        JOIN statement_categories sc ON d.statement_id = sc.statement_id
        WHERE sc.status = 'ACTIVE'
          AND d.status = 'APPROVE'
          AND d.document_id NOT IN (
              SELECT document_id 
              FROM random_qc_results
          )
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def _get_pdf_text(document_id):
    """Get PDF text for a document from DB cache."""
    conn = get_connection()
    cursor = get_cursor(conn)
    
    cursor.execute("""
        SELECT extracted_text 
        FROM document_text_extractions 
        WHERE document_id = %s 
        ORDER BY created_at DESC LIMIT 1
    """, (document_id,))
    row = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    if row and row["extracted_text"]:
        return row["extracted_text"]
    
    return None


def _get_stored_transactions(document_id, parser_type):
    """
    Get stored transactions from ai_transactions_staging.
    parser_type = 'CODE' or 'LLM'
    Returns a Python list of transaction dicts, or None if not found.
    """
    conn = get_connection()
    cursor = get_cursor(conn)
    cursor.execute("""
        SELECT transaction_json
        FROM ai_transactions_staging
        WHERE document_id = %s AND parser_type = %s
        ORDER BY created_at DESC LIMIT 1
    """, (document_id, parser_type))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if row and row["transaction_json"]:
        return safe_json_loads(row["transaction_json"])
    return None


def _save_llm_transactions(document_id, statement_id, llm_txns):
    """
    Save LLM transactions to ai_transactions_staging.
    Called only when a document had no LLM transactions before
    (Scenario B: code-only documents).
    """
    # Get user_id from the document
    conn = get_connection()
    cursor = get_cursor(conn)
    cursor.execute("SELECT user_id FROM documents WHERE document_id = %s", (document_id,))
    doc_row = cursor.fetchone()
    user_id = doc_row["user_id"] if doc_row else 1
    
    cursor.execute("""
        INSERT INTO ai_transactions_staging
        (document_id, user_id, parser_type, transaction_json, overall_confidence)
        VALUES (%s, %s, 'LLM', %s, %s)
    """, (document_id, user_id, json.dumps(llm_txns), 0.95))
    conn.commit()
    cursor.close()
    conn.close()


def _save_qc_result(document_id, statement_id, file_name, institution_name,
                     code_txns, llm_txns, reconciliation):
    """Save a single QC result to the random_qc_results table."""
    summary = reconciliation["summary"]
    accuracy = float(reconciliation["overall_similarity"])
    
    # Accuracy threshold: 98% or above is acceptable
    qc_status = 'REVIEWED' if accuracy >= 98.0 else 'FLAGGED'
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Save the QC result
        cursor.execute("""
            INSERT INTO random_qc_results 
            (document_id, statement_id, file_name, institution_name,
             code_txn_count, llm_txn_count, matched_count,
             unmatched_code_count, unmatched_llm_count, accuracy,
             qc_status, reconciliation_json, code_txn_json, llm_txn_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            document_id, statement_id, file_name, institution_name,
            summary["total_code"], summary["total_llm"], summary["matched_count"],
            summary["unmatched_code_count"], summary["unmatched_llm_count"],
            accuracy,
            qc_status,
            json.dumps(reconciliation),
            json.dumps(code_txns),
            json.dumps(llm_txns)
        ))
        
        # 2. 🚨 If FLAGGED, demote the logic to EXPERIMENTAL so it appears in Review Document
        if qc_status == 'FLAGGED':
            logger.warning(f"  🚨 AUTO-DEMOTING statement_id {statement_id} to EXPERIMENTAL due to low accuracy ({accuracy}%)")
            cursor.execute("""
                UPDATE statement_categories 
                SET status = 'EXPERIMENTAL' 
                WHERE statement_id = %s
            """, (statement_id,))
        elif qc_status == 'REVIEWED':
            logger.info(f"  ✅ PROMOTING statement_id {statement_id} to REVIEWED due to high accuracy ({accuracy}%)")
            cursor.execute("""
                UPDATE statement_categories 
                SET status = 'REVIEWED' 
                WHERE statement_id = %s
            """, (statement_id,))
            
        conn.commit()
    except Exception as e:
        logger.error(f"  Error in _save_qc_result for doc {document_id}: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


def run_random_qc(sample_size=1):
    """
    Main function called by the scheduler.
    Picks random ACTIVE documents, gets stored Code transactions,
    checks for existing LLM transactions (calls LLM if missing),
    reconciles them, and saves QC results.
    """
    logger.info(f"Starting random QC check (sample_size={sample_size})...")
    
    # 1. Get all eligible documents
    all_docs = _get_active_documents()
    
    if not all_docs:
        logger.warning("No active documents found for random QC.")
        return {"checked": 0, "message": "No active documents found"}
    
    # 2. Randomly pick documents
    if len(all_docs) <= sample_size:
        selected = all_docs
    else:
        selected = random.sample(all_docs, sample_size)
    
    logger.info(f"Selected {len(selected)} documents for QC check.")
    
    results = []
    
    # 3. Process each selected document
    for doc in selected:
        doc_id = doc["document_id"]
        stmt_id = doc["statement_id"]
        file_name = doc["file_name"] or f"doc_{doc_id}.pdf"
        institution = doc["institution_name"] or "Unknown"
        identifier_json_str = doc["statement_identifier"]
        
        logger.info(f"  Processing document {doc_id} ({file_name})...")
        
        try:
            # 3a. Get PDF text (needed only if we have to call LLM)
            pdf_text = _get_pdf_text(doc_id)
            if not pdf_text:
                file_path = doc.get("file_path")
                if file_path:
                    logger.info(f"  No cached PDF text. Extracting directly from file: {file_path}")
                    # Check for password
                    conn2 = get_connection()
                    cursor2 = get_cursor(conn2)
                    cursor2.execute("SELECT encrypted_password FROM document_password WHERE document_id = %s", (doc_id,))
                    pwd_row = cursor2.fetchone()
                    cursor2.close()
                    conn2.close()
                    password = pwd_row["encrypted_password"] if pwd_row else None
                    try:
                        pdf_text = extract_full_text(file_path, password)
                    except Exception as e:
                        logger.error(f"Failed to extract PDF text from {file_path}: {e}")
            
            if not pdf_text:
                logger.warning(f"  Still no PDF text found for document {doc_id}. Skipping.")
                continue
            
            # 3b. ALWAYS run the LATEST extraction_logic fresh against the PDF text.
            #     This ensures that if the code was improved & saved in Review Document,
            #     Random QC uses the updated code, not stale stored transactions.
            extraction_logic = doc.get("extraction_logic")
            code_txns = None
            used_fresh = False
            
            if extraction_logic:
                try:
                    logger.info(f"  Running FRESH extraction_logic for doc {doc_id}...")
                    code_txns = extract_transactions_using_logic(pdf_text, extraction_logic)
                    if code_txns:
                        logger.info(f"  Fresh extraction returned {len(code_txns)} transactions.")
                        used_fresh = True
                    else:
                        logger.warning(f"  Fresh extraction returned 0 transactions.")
                except Exception as e:
                    logger.warning(f"  Fresh extraction failed for doc {doc_id}: {e}. Falling back to stored txns.")
            
            # Fallback: use stored CODE transactions if fresh extraction failed
            if not code_txns:
                code_txns = _get_stored_transactions(doc_id, "CODE")
                if code_txns:
                    logger.info(f"  Using {len(code_txns)} stored CODE transactions as fallback.")

            if not code_txns:
                logger.warning(f"  No CODE transactions for document {doc_id}. Skipping.")
                continue
            
            # 3b-sync. If we used fresh extraction, update the staging table
            #          so the Review Document page shows the same data as QC.
            if used_fresh:
                try:
                    conn_sync = get_connection()
                    cursor_sync = get_cursor(conn_sync)
                    cursor_sync.execute("SELECT user_id FROM documents WHERE document_id = %s", (doc_id,))
                    uid_row = cursor_sync.fetchone()
                    uid = uid_row["user_id"] if uid_row else 1
                    cursor_sync.execute("""
                        INSERT INTO ai_transactions_staging
                        (document_id, user_id, parser_type, transaction_json, overall_confidence)
                        VALUES (%s, %s, 'CODE', %s, %s)
                    """, (doc_id, uid, json.dumps(code_txns), 1.0))
                    conn_sync.commit()
                    cursor_sync.close()
                    conn_sync.close()
                    logger.info(f"  Synced {len(code_txns)} fresh CODE txns to staging for doc {doc_id}.")
                except Exception as e:
                    logger.warning(f"  Failed to sync fresh CODE txns to staging for doc {doc_id}: {e}")
            
            # 3c. Get STORED LLM transactions from DB
            llm_txns = _get_stored_transactions(doc_id, "LLM")
            
            # 3d. If no LLM transactions → call LLM parser and save them
            if not llm_txns:
                logger.info(f"  No LLM transactions found for doc {doc_id}. Calling LLM parser...")
                identifier_json = safe_json_loads(identifier_json_str) if isinstance(identifier_json_str, str) else identifier_json_str
                llm_response = parse_with_llm(pdf_text, identifier_json)
                llm_txns = extract_json_from_response(llm_response)
                
                # Save the LLM transactions to ai_transactions_staging
                if llm_txns:
                    _save_llm_transactions(doc_id, stmt_id, llm_txns)
                    logger.info(f"  LLM extracted {len(llm_txns)} transactions. Saved to staging.")
                else:
                    logger.warning(f"  LLM returned no transactions for doc {doc_id}.")
                    llm_txns = []
            else:
                logger.info(f"  Found {len(llm_txns)} existing LLM transactions in DB.")
            
            # 3e. Reconcile Code vs LLM
            reconciliation = reconcile_transactions(code_txns, llm_txns)
            
            # 3f. Save QC result
            _save_qc_result(
                doc_id, stmt_id, file_name, institution,
                code_txns, llm_txns, reconciliation
            )
            
            accuracy = reconciliation["overall_similarity"]
            logger.info(f"  Document {doc_id}: accuracy={accuracy}%")
            results.append({"document_id": doc_id, "accuracy": accuracy})
            
        except Exception as e:
            logger.error(f"  Error processing document {doc_id}: {str(e)}")
            continue
    
    # 4. Summary
    if results:
        avg = sum(r["accuracy"] for r in results) / len(results)
        logger.info(f"Random QC complete: {len(results)} documents checked, avg accuracy={avg:.1f}%")
    else:
        logger.info("Random QC complete: No documents were successfully checked.")
    
    return {"checked": len(results), "results": results}
