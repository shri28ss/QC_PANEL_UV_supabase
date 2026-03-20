"""
Supabase Storage Service
Handles file uploads and downloads from Supabase Storage
"""
import os
import tempfile
from typing import Optional
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_ANON_KEY

# Default bucket name - update this to match your Supabase bucket
DEFAULT_BUCKET = "financial_document_uploads"

def get_supabase_client() -> Client:
    """Initialize Supabase client"""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise Exception("SUPABASE_URL and SUPABASE_ANON_KEY must be set in .env")
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

def download_pdf_from_storage(file_path: str, bucket_name: str = None) -> Optional[str]:
    """
    Download PDF from Supabase Storage to a temporary file.

    Args:
        file_path: The storage path (e.g., "documents/user_1/file.pdf" or "user_1/file.pdf")
        bucket_name: Optional bucket name. If not provided, uses DEFAULT_BUCKET

    Returns:
        Path to the temporary file, or None if download fails
    """
    try:
        supabase = get_supabase_client()

        # Determine bucket and storage path
        if "/" in file_path and not bucket_name:
            # Check if first part looks like a bucket name
            parts = file_path.split("/", 1)
            first_part = parts[0]

            # If it looks like a UUID or path (not a bucket), use default bucket
            if len(first_part) > 20 or "-" in first_part:
                bucket = DEFAULT_BUCKET
                storage_path = file_path
            else:
                # First part might be bucket name
                bucket = first_part
                storage_path = parts[1] if len(parts) > 1 else file_path
        else:
            bucket = bucket_name or DEFAULT_BUCKET
            storage_path = file_path

        print(f"Attempting to download from bucket '{bucket}', path '{storage_path}'")

        # Download file from Supabase Storage
        response = supabase.storage.from_(bucket).download(storage_path)

        if not response:
            print(f"Failed to download file from storage: {file_path}")
            return None

        # Save to temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        temp_file.write(response)
        temp_file.close()

        print(f"Successfully downloaded to: {temp_file.name}")
        return temp_file.name

    except Exception as e:
        print(f"Error downloading from Supabase Storage: {e}")
        return None

def is_supabase_storage_path(file_path: str) -> bool:
    """
    Check if the file_path is a Supabase Storage path.

    Returns True if it looks like a storage path (doesn't start with / or C:)
    """
    if not file_path:
        return False

    # Local paths typically start with / (Unix) or C:\ (Windows)
    if file_path.startswith("/") or (len(file_path) > 1 and file_path[1] == ":"):
        return False

    # Storage paths typically look like "bucket/path/file.pdf" or "uuid/file.pdf"
    return True

def get_pdf_local_path(file_path: str) -> Optional[str]:
    """
    Get local file path for a PDF.
    - If it's a local path and exists, return it
    - If it's a Supabase Storage path, download it and return temp path
    - Otherwise return None
    """
    if not file_path:
        return None

    # Check if it's a local file that exists
    if os.path.exists(file_path):
        return file_path

    # Check if it's a Supabase Storage path
    if is_supabase_storage_path(file_path):
        return download_pdf_from_storage(file_path)

    return None
