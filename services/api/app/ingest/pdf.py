"""PDF handling (DESIGN.md 6.2).

Two failure states matter enough to be named rather than raised as generic
errors, because the UI has to respond differently to each:

- `NEEDS_PASSWORD` — the file is encrypted. The UI asks for the password with
  the bank-specific hint and retries.
- `NO_TEXT_LAYER` — the file is a scan. There is no text to parse, and saying
  so plainly beats returning zero transactions and letting the user conclude
  their statement was empty.

The password is held in memory for the duration of the decryption and is never
written to a file, a log line or an exception message.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import pikepdf
import pdfplumber

from .adapters.base import ParseError


@dataclass(frozen=True)
class PdfText:
    text: str
    page_count: int
    was_encrypted: bool


def is_encrypted(data: bytes) -> bool:
    try:
        with pikepdf.open(io.BytesIO(data)):
            return False
    except pikepdf.PasswordError:
        return True
    except pikepdf.PdfError as exc:
        raise ParseError("CORRUPT_PDF", "This file is not a readable PDF.") from exc


def _decrypt(data: bytes, password: str | None) -> bytes:
    """Return decrypted bytes, or the original if the file was never encrypted.

    Note the bare `except pikepdf.PasswordError` below: the exception is
    re-raised as our own error without chaining, because pikepdf's message can
    echo back what was attempted and this function is the one place a password
    is in scope.
    """
    try:
        with pikepdf.open(io.BytesIO(data)) as pdf:
            del pdf
        return data
    except pikepdf.PasswordError:
        pass
    except pikepdf.PdfError as exc:
        raise ParseError("CORRUPT_PDF", "This file is not a readable PDF.") from exc

    if not password:
        raise ParseError(
            "NEEDS_PASSWORD",
            "This statement is password protected.",
            hint="Enter the password your bank uses for statement PDFs.",
        )
    try:
        with pikepdf.open(io.BytesIO(data), password=password) as pdf:
            buffer = io.BytesIO()
            pdf.save(buffer)
            return buffer.getvalue()
    except pikepdf.PasswordError:
        raise ParseError(
            "WRONG_PASSWORD",
            "That password did not open the statement.",
            hint="Check the format your bank uses.",
        ) from None
    except pikepdf.PdfError as exc:
        raise ParseError("CORRUPT_PDF", "This file is not a readable PDF.") from exc


def extract_text(data: bytes, password: str | None = None) -> PdfText:
    encrypted = is_encrypted(data)
    decrypted = _decrypt(data, password)

    pages: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(decrypted)) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
    except Exception as exc:  # pdfplumber raises a wide variety on damaged files
        raise ParseError("CORRUPT_PDF", "This PDF could not be read.") from exc

    text = "\n".join(pages).strip()
    if not text:
        raise ParseError(
            "NO_TEXT_LAYER",
            "This PDF has no text layer — it looks like a scan or photo.",
            hint="Upload the CSV export from your bank instead.",
        )
    return PdfText(text=text, page_count=len(pages), was_encrypted=encrypted)
