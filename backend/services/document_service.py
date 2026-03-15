# document_service.py

import os
from typing import Dict, Any, List

from repository.document_repo import (
    create_document,
    update_document_status,
    link_statement_to_document,
    insert_upload_audit,
    save_extracted_text,
    insert_statement_transactions,
    save_document_password
)

from services.review_service import run_review_engine


# ==========================================================
# MAIN DOCUMENT PROCESSOR
# ==========================================================

def process_document(
    user_id: int,
    file_path: str,
    extracted_text: str,
    statement_id: int,
    extracted_transactions: List[Dict],
    password: str = None
) -> Dict[str, Any]:

    file_name = os.path.basename(file_path)

    # ------------------------------------------------------
    # 1️⃣ Create Document Entry
    # ------------------------------------------------------
    document_id = create_document(
        user_id=user_id,
        file_name=file_name,
        file_path=file_path,
        is_password_protected=bool(password)
    )

    insert_upload_audit(document_id, "UPLOADED")

    try:
        # Save extracted text and transactions
        save_extracted_text(document_id, extracted_text)
        insert_statement_transactions(document_id, extracted_transactions)

        if password:
            save_document_password(document_id, password)

        link_statement_to_document(document_id, statement_id)

        # Run review engine
        review_result = run_review_engine(document_id, extracted_text, extracted_transactions)

        # ------------------------------------------------------
        # 8️⃣ Keep It Under Review (admin must decide)
        # ------------------------------------------------------
        update_document_status(document_id, "UNDER_REVIEW")
        insert_upload_audit(document_id, "COMPLETED")

        return {
            "document_id": document_id,
            "review_result": review_result
        }

    except Exception as e:

        # If processing fails → disable it
        update_document_status(document_id, "DISABLED")
        insert_upload_audit(document_id, "FAILED", str(e))

        raise e