"""
Supabase Storage Service
Handles file uploads and downloads from Supabase Storage.

Download strategy (in order):
  1. Service role key (bypasses RLS - requires SUPABASE_SERVICE_ROLE_KEY in .env)
  2. Signed URL (temporary URL that works even with RLS enabled)
  3. Direct anon key download (may fail due to RLS)
"""
import os
import tempfile
import requests
from typing import Optional
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_ANON_KEY

# Default bucket name
DEFAULT_BUCKET = "financial_document_uploads"

# Service role key - bypasses RLS for backend/server-side operations
# Set this in your .env as: SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")


def get_supabase_client() -> Client:
    """Initialize Supabase client using anon key (general use)."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise Exception("SUPABASE_URL and SUPABASE_ANON_KEY must be set in .env")
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def get_admin_supabase_client() -> Client:
    """
    Initialize Supabase client using service role key.
    Bypasses Row Level Security (RLS). Safe for server-side use only.
    Falls back to anon key if SUPABASE_SERVICE_ROLE_KEY is not configured.
    """
    if SUPABASE_SERVICE_ROLE_KEY:
        return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    print("WARNING: SUPABASE_SERVICE_ROLE_KEY not set. Using anon key (may fail due to RLS).")
    return get_supabase_client()


def download_pdf_from_storage(file_path: str, bucket_name: str = None) -> Optional[str]:
    """
    Download a PDF from Supabase Storage to a local temp file.

    Tries three strategies in order:
      1. Service role key (bypasses RLS)
      2. Signed URL via anon key
      3. Direct download via anon key

    Args:
        file_path: Storage path like "user_id/document_id_filename.pdf"
        bucket_name: Optional override. Defaults to DEFAULT_BUCKET.

    Returns:
        Local temp file path, or None if all strategies fail.
    """
    try:
        # Resolve bucket and storage path
        if "/" in file_path and not bucket_name:
            parts = file_path.split("/", 1)
            first_part = parts[0]
            if len(first_part) > 20 or "-" in first_part:
                # Looks like a UUID user_id, not a bucket name
                bucket = DEFAULT_BUCKET
                storage_path = file_path
            else:
                bucket = first_part
                storage_path = parts[1] if len(parts) > 1 else file_path
        else:
            bucket = bucket_name or DEFAULT_BUCKET
            storage_path = file_path

        print(f"Attempting to download from bucket '{bucket}', path '{storage_path}'")

        # --- Strategy 1: Service role key (bypasses RLS) ---
        if SUPABASE_SERVICE_ROLE_KEY:
            try:
                admin_client = get_admin_supabase_client()
                response = admin_client.storage.from_(bucket).download(storage_path)
                if response:
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                    temp_file.write(response)
                    temp_file.close()
                    print(f"Downloaded via service role key: {temp_file.name}")
                    return temp_file.name
            except Exception as e:
                print(f"Service role download failed, trying signed URL: {e}")

        # --- Strategy 2: Signed URL (works with RLS if bucket allows signed URLs) ---
        try:
            anon_client = get_supabase_client()
            signed = anon_client.storage.from_(bucket).create_signed_url(storage_path, expires_in=300)

            # Handle different supabase-py versions' response formats
            signed_url = None
            if isinstance(signed, dict):
                # v1 style: {'signedURL': '...'} or v2 style: {'data': {'signedUrl': '...'}, 'error': None}
                signed_url = (
                    signed.get("signedURL")
                    or signed.get("signedUrl")
                    or (signed.get("data") or {}).get("signedUrl")
                    or (signed.get("data") or {}).get("signedURL")
                )
            elif hasattr(signed, "signed_url"):
                # Object-style response
                signed_url = signed.signed_url
            elif hasattr(signed, "data") and hasattr(signed.data, "signed_url"):
                signed_url = signed.data.signed_url

            print(f"Signed URL result: {str(signed)[:200]}")

            if signed_url:
                r = requests.get(signed_url, timeout=30)
                if r.status_code == 200:
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                    temp_file.write(r.content)
                    temp_file.close()
                    print(f"Downloaded via signed URL: {temp_file.name}")
                    return temp_file.name
                else:
                    print(f"Signed URL HTTP error: {r.status_code}")
            else:
                print(f"Could not extract signed URL from response: {signed}")
        except Exception as e:
            print(f"Signed URL approach failed: {e}")


        # --- Strategy 3: Direct anon key download (may fail due to RLS) ---
        try:
            anon_client = get_supabase_client()
            response = anon_client.storage.from_(bucket).download(storage_path)
            if response:
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                temp_file.write(response)
                temp_file.close()
                print(f"Downloaded via anon key: {temp_file.name}")
                return temp_file.name
        except Exception as e:
            print(f"Anon key direct download failed: {e}")

        print(f"All download strategies failed for: {file_path}")
        return None

    except Exception as e:
        print(f"Error in download_pdf_from_storage: {e}")
        return None


def is_supabase_storage_path(file_path: str) -> bool:
    """
    Check if the file_path is a Supabase Storage path.
    Returns True if it doesn't look like a local OS file path.
    """
    if not file_path:
        return False
    if file_path == "pending_upload":
        return False
    # Local paths start with / (Unix) or X: (Windows drive letter)
    if file_path.startswith("/") or (len(file_path) > 1 and file_path[1] == ":"):
        return False
    return True


def get_pdf_local_path(file_path: str) -> Optional[str]:
    """
    Resolve a PDF to a local path.
    - Returns the path directly if it's a local file that exists.
    - Downloads from Supabase Storage if it's a storage path.
    - Returns None if the file cannot be resolved.
    """
    if not file_path:
        return None

    if file_path == "pending_upload":
        return None

    # Local file already exists
    if os.path.exists(file_path):
        return file_path

    # Download from Supabase Storage
    if is_supabase_storage_path(file_path):
        return download_pdf_from_storage(file_path)

    return None
