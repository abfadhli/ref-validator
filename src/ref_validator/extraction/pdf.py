"""PDF text extraction using PyMuPDF."""

import asyncio
from pathlib import Path

import pymupdf

from ref_validator.errors import PDFExtractionError


def extract_text_sync(pdf_path: Path) -> str:
    """Extract text from a PDF file synchronously."""
    try:
        doc = pymupdf.open(str(pdf_path))
    except Exception as e:
        raise PDFExtractionError(f"Failed to open PDF: {e}") from e

    try:
        pages = []
        for page in doc:
            text = page.get_text()
            if text.strip():
                pages.append(text)
        if not pages:
            raise PDFExtractionError("No text content found in PDF")
        return "\n\n".join(pages)
    finally:
        doc.close()


async def extract_text(pdf_path: Path) -> str:
    """Extract text from a PDF file (async wrapper)."""
    return await asyncio.to_thread(extract_text_sync, pdf_path)
