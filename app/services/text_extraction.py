from __future__ import annotations

import io
import re
from typing import Callable

import pandas as pd
import pdfplumber
from docx import Document

SUPPORTED_EXTENSIONS = {"txt", "docx", "pdf", "csv"}
_WHITESPACE_RE = re.compile(r"\s+")


class UnsupportedFileTypeError(ValueError):
    """Raised when attempting to extract text from an unsupported file type."""


def _extract_txt(data: bytes) -> str:
    return data.decode("utf-8", errors="ignore")


def _extract_docx(data: bytes) -> str:
    stream = io.BytesIO(data)
    document = Document(stream)
    paragraphs = [p.text.strip() for p in document.paragraphs if p.text and p.text.strip()]
    return "\n".join(paragraphs)


def _extract_pdf(data: bytes) -> str:
    stream = io.BytesIO(data)
    texts: list[str] = []
    with pdfplumber.open(stream) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text:
                texts.append(page_text.strip())
    return "\n".join(texts)


def _extract_csv(data: bytes) -> str:
    stream = io.BytesIO(data)
    df = pd.read_csv(stream, dtype=str, keep_default_na=False)
    cells: list[str] = []
    for value in df.to_numpy().flatten():
        if value is None:
            continue
        text_value = str(value).strip()
        if text_value:
            cells.append(text_value)
    return "\n".join(cells)


_EXTRACTORS: dict[str, Callable[[bytes], str]] = {
    "txt": _extract_txt,
    "docx": _extract_docx,
    "pdf": _extract_pdf,
    "csv": _extract_csv,
}


def normalize_text(text: str) -> str:
    """Normalize whitespace for consistent downstream handling."""
    return _WHITESPACE_RE.sub(" ", text).strip()


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract normalized text for supported file extensions."""
    if not filename or "." not in filename:
        raise UnsupportedFileTypeError("Filename must contain an extension.")
    ext = filename.rsplit(".", 1)[1].lower()
    extractor = _EXTRACTORS.get(ext)
    if extractor is None:
        raise UnsupportedFileTypeError(f"Unsupported file extension: {ext}")
    raw_text = extractor(file_bytes)
    return normalize_text(raw_text)


def word_count(text: str) -> int:
    """Return the approximate word count for the provided text."""
    if not text:
        return 0
    return len(text.split())

