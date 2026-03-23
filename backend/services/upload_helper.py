"""
Helper function to upload files to Supabase Storage.
Uses the service role key (bypasses RLS) so uploads always succeed server-side.
"""
from services.storage_service import get_admin_supabase_client
import uuid

def upload_pdf_to_supabase(file_bytes: bytes, user_id: str, original_filename: str, document_id=None) -> str:
    """
    Upload a PDF file to Supabase Storage under a user-specific folder.

    Folder structure in bucket:
        financial_document_uploads/
            {user_id}/
                {document_id}_{original_filename}.pdf   ← if document_id provided
                {24char_uuid}.pdf                       ← fallback

    Args:
        file_bytes: Raw PDF bytes
        user_id: The user's UUID (used as folder name)
        original_filename: Original file name (e.g., "bank_statement.pdf")
        document_id: DB document_id, used to name the file for easy mapping

    Returns:
        storage_path: e.g. "72fede0b-.../22_bank_statement.pdf"
    """
    # Use admin client (service role key) to bypass Supabase RLS on uploads
    client = get_admin_supabase_client()

    if document_id:
        # Clean the filename to avoid path issues
        safe_name = original_filename.replace("/", "_").replace("\\", "_")
        file_name = f"{document_id}_{safe_name}"
    else:
        file_id = str(uuid.uuid4()).replace("-", "")[:24]
        file_name = f"{file_id}.pdf"

    storage_path = f"{user_id}/{file_name}"

    client.storage.from_("financial_document_uploads").upload(
        path=storage_path,
        file=file_bytes,
        file_options={"content-type": "application/pdf"}
    )

    print(f"[Storage] Uploaded: {storage_path}")
    return storage_path



# Example usage for Streamlit or custom scripts:
#
# if uploaded_file and st.button("Start Processing"):
#     file_bytes = uploaded_file.read()
#
#     # 1. Save to database FIRST to get the document ID
#     query = """
#         INSERT INTO documents
#         (user_id, file_name, file_path, is_password_protected, status)
#         VALUES (%s, %s, %s, %s, 'UPLOADED')
#     """
#     document_id = execute_insert(conn, cursor, query, (
#         st.session_state.user_id,
#         uploaded_file.name,
#         "pending_upload",  # temporary
#         bool(password)
#     ))
#
#     # 2. Upload to Supabase Storage using the assigned document_id
#     storage_path = upload_pdf_to_supabase(
#         file_bytes=file_bytes,
#         user_id=str(st.session_state.user_id),
#         original_filename=uploaded_file.name,
#         document_id=document_id
#     )
#
#     # 3. Update the file_path in the documents table
#     cursor.execute("UPDATE documents SET file_path = %s WHERE document_id = %s", (storage_path, document_id))
#
#     # 4. Map the password securely using the document_id
#     if password:
#         cursor.execute("INSERT INTO document_password (document_id, encrypted_password) VALUES (%s, %s)", (document_id, password))
#
#     conn.commit()
