import pdfplumber
from typing import List, Optional
from services.storage_service import get_pdf_local_path

def extract_pages(pdf_path: str, password: Optional[str] = None) -> List[str]:
    """Extract text from all pages of PDF"""
    # Get local path (downloads from Supabase if needed)
    local_path = get_pdf_local_path(pdf_path)
    if not local_path:
        raise Exception(f"Could not access PDF file: {pdf_path}")

    pages = []
    with pdfplumber.open(local_path, password=password) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                pages.append(t)
    return pages

def extract_full_text(pdf_path: str, password: Optional[str] = None) -> str:
    """Return full PDF text"""
    return "\n".join(extract_pages(pdf_path, password))