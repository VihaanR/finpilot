"""Bank password hints (DESIGN.md 6.2).

Indian bank statements arrive encrypted by default and users do not know their
own password *format* — it is set by the bank, not chosen. Asking for "the
password" with no hint is the single most common place an upload flow dies, so
the hint is part of the API rather than a UI string.

Passwords are used in memory for decryption and never persisted, never logged.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BankHint:
    bank_code: str
    bank_name: str
    #: Several, because some banks use different formats depending on whether
    #: the statement came from net banking, email or the mobile app.
    formats: tuple[str, ...]
    example: str | None = None


BANK_HINTS: tuple[BankHint, ...] = (
    BankHint("HDFC", "HDFC Bank", ("Your Customer ID",), "52xxxxxx"),
    BankHint(
        "ICICI",
        "ICICI Bank",
        ("First 4 letters of your name in lowercase, then DDMM of your date of birth",),
        "viha1503",
    ),
    BankHint(
        "SBI",
        "State Bank of India",
        (
            "Net banking: your registered date of birth as DDMMYYYY",
            "Email statement: the last 5 digits of your account number",
            "YONO: your profile password",
        ),
    ),
    BankHint(
        "AXIS",
        "Axis Bank",
        ("First 4 letters of your name in uppercase, then DDMM of your date of birth",),
        "VIHA1503",
    ),
    BankHint("KOTAK", "Kotak Mahindra Bank", ("Your Customer Relationship Number (CRN)",)),
    BankHint(
        "PNB",
        "Punjab National Bank",
        ("Your account number", "Your registered mobile number", "Your PAN"),
    ),
    BankHint(
        "BOB",
        "Bank of Baroda",
        ("Your account number", "Your registered mobile number", "Your PAN"),
    ),
    BankHint(
        "BOI",
        "Bank of India",
        ("Your account number", "Your registered mobile number", "Your PAN"),
    ),
    BankHint("IDFC", "IDFC FIRST Bank", ("First 4 letters of your name, then DDMM of birth",)),
    BankHint("YES", "YES Bank", ("Your Customer ID",)),
    BankHint("INDUSIND", "IndusInd Bank", ("Your date of birth as DDMMYYYY",)),
    BankHint("CANARA", "Canara Bank", ("Your registered mobile number",)),
)

_BY_CODE = {hint.bank_code: hint for hint in BANK_HINTS}

GENERIC_HINT = BankHint(
    "UNKNOWN",
    "Your bank",
    (
        "Commonly your Customer ID, your date of birth as DDMMYYYY, "
        "or the first 4 letters of your name followed by DDMM",
    ),
)


def hint_for(bank_code: str | None) -> BankHint:
    if not bank_code:
        return GENERIC_HINT
    return _BY_CODE.get(bank_code.strip().upper(), GENERIC_HINT)


def detect_bank(text: str, filename: str = "") -> str | None:
    """Best guess at the issuing bank from statement text or the file name."""
    haystack = (text[:4000] + " " + filename).upper()
    for code, needles in (
        ("HDFC", ("HDFC BANK", "HDFC0")),
        ("ICICI", ("ICICI BANK", "ICIC0")),
        ("SBI", ("STATE BANK OF INDIA", "SBIN0")),
        ("AXIS", ("AXIS BANK", "UTIB0")),
        ("KOTAK", ("KOTAK MAHINDRA", "KKBK0")),
        ("PNB", ("PUNJAB NATIONAL BANK", "PUNB0")),
        ("BOB", ("BANK OF BARODA", "BARB0")),
        ("BOI", ("BANK OF INDIA", "BKID0")),
        ("IDFC", ("IDFC FIRST", "IDFB0")),
        ("YES", ("YES BANK", "YESB0")),
        ("INDUSIND", ("INDUSIND BANK", "INDB0")),
        ("CANARA", ("CANARA BANK", "CNRB0")),
    ):
        if any(needle in haystack for needle in needles):
            return code
    return None
