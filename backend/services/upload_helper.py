"""
Helper function to upload files to Supabase Storage
Add this to your upload logic
"""
from services.storage_service import get_supabase_client
import uuid

def upload_pdf_to_supabase(file_bytes: bytes, user_id: str, original_filename: str) -> str:
    """
    Upload a PDF file to Supabase Storage.

    Args:
        file_bytes: The PDF file content as bytes
        user_id: User ID (can be UUID or user identifier)
        original_filename: Original filename (e.g., "statement.pdf")

    Returns:
        The storage path (e.g., "user_id/file_id.pdf")
    """
    client = get_supabase_client()

    # Generate unique file ID
    file_id = str(uuid.uuid4()).replace('-', '')[:24]

    # Create storage path: user_id/file_id.pdf
    storage_path = f"{user_id}/{file_id}.pdf"

    # Upload to Supabase Storage
    result = client.storage.from_("financial_document_uploads").upload(
        path=storage_path,
        file=file_bytes,
        file_options={"content-type": "application/pdf"}
    )

    print(f"Uploaded to Supabase Storage: {storage_path}")

    return storage_path


# Example usage in your upload.py:
#
# if uploaded_file and st.button("Start Processing"):
#     file_bytes = uploaded_file.read()
#
#     # Upload to Supabase Storage
#     storage_path = upload_pdf_to_supabase(
#         file_bytes=file_bytes,
#         user_id=str(st.session_state.user_id),
#         original_filename=uploaded_file.name
#     )
#
#     # Save to database with storage path
#     query = """
#         INSERT INTO documents
#         (user_id, file_name, file_path, is_password_protected, status)
#         VALUES (%s, %s, %s, %s, 'UPLOADED')
#     """
#     document_id = execute_insert(conn, cursor, query, (
#         st.session_state.user_id,
#         uploaded_file.name,
#         storage_path,  # <-- Use storage path instead of local path
#         bool(password)
#     ))
