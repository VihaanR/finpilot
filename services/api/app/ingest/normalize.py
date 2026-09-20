"""Narration normalisation (DESIGN.md section 6).

A bank statement gives us one opaque string per row. This module turns it into
the four facts the rest of the product needs: who the counterparty was, which
rail carried the money, which way it moved, and a canonical form of the
narration that is stable across transactions.

That last one matters more than it looks. Every narration carries a unique
reference number, so hashing the raw string would give a fresh key every time
and the tier-2 classification cache (DESIGN.md section 7) would never hit. The
canonical form strips the volatile parts, which is what makes "each unique
narration shape costs exactly one classification" true.

Pure functions over strings. No database, no network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from ..engine.types import Channel, Direction

# --- Money ------------------------------------------------------------------

_AMOUNT_CLEAN_RE = re.compile(r"[^\d.\-]")


def to_paise(value: str | int | Decimal) -> int:
    """Rupee amount -> integer paise (DESIGN.md 5.1, invariant 1).

    Routed through `Decimal` rather than `float` on purpose: `int(1725.55 * 100)`
    is 172554, and a statement full of those quietly loses rupees. A `float`
    argument is rejected outright rather than silently coerced.
    """
    if isinstance(value, bool):
        raise TypeError("bool is not an amount")
    if isinstance(value, float):
        raise TypeError("refusing float: pass the string from the statement")
    if isinstance(value, int):
        return value * 100
    text = _AMOUNT_CLEAN_RE.sub("", str(value).strip())
    if not text or text in {"-", ".", "-."}:
        raise ValueError("not an amount: {0!r}".format(value))
    try:
        return int((Decimal(text) * 100).to_integral_value())
    except (InvalidOperation, ArithmeticError) as exc:
        raise ValueError("not an amount: {0!r}".format(value)) from exc


# --- Channel ----------------------------------------------------------------

#: Ordered, because narrations nest: "TO TRANSFER-UPI/DR/..." is a UPI payment
#: worded as a transfer, and "E-MANDATE" rides a card rail even though it reads
#: like a bank mandate. First match wins, so specific markers come first.
_CHANNEL_MARKERS: tuple[tuple[re.Pattern[str], Channel], ...] = (
    (re.compile(r"E-?MANDATE|AUTOPAY"), Channel.CARD),
    (re.compile(r"\bUPI\b"), Channel.UPI),
    (re.compile(r"\bACH\s*[DC]?-|\bNACH\b"), Channel.NACH),
    (re.compile(r"\bSI-|STANDING\s+INSTRUCTION"), Channel.NACH),
    (re.compile(r"\bNEFT\b"), Channel.NEFT),
    (re.compile(r"\bIMPS\b"), Channel.IMPS),
    (re.compile(r"\bRTGS\b"), Channel.NEFT),
    (re.compile(r"\bATW\b|\bATM\b|\bNWD\b|CASH\s+WDL"), Channel.ATM),
    (re.compile(r"\bPOS\b|\bECOM\b|\bCARD\b|\bVISA\b|MASTERCARD"), Channel.CARD),
    (re.compile(r"\bCHQ\b|CHEQUE|\bCLG\b"), Channel.CHEQUE),
    (re.compile(r"\bCASH\b"), Channel.CASH),
)


def classify_channel(raw: str) -> Channel:
    upper = raw.upper()
    for pattern, channel in _CHANNEL_MARKERS:
        if pattern.search(upper):
            return channel
    if "@" in raw:
        return Channel.UPI
    return Channel.OTHER


# --- VPA --------------------------------------------------------------------

_VPA_RE = re.compile(r"([a-z0-9][a-z0-9._-]{1,63})@([a-z][a-z0-9.]{1,63})", re.I)

#: Handles that identify a payment service provider rather than a merchant.
#: Treating "okhdfcbank" as the counterparty would collapse every UPI payment
#: routed through HDFC into a single merchant.
_PSP_HANDLES = frozenset(
    {
        "ybl", "okaxis", "okhdfcbank", "okicici", "oksbi", "paytm", "apl",
        "upi", "ibl", "axl", "icici", "hdfcbank", "sbi", "axisbank", "yesbank",
        "kotak", "idfcbank", "airtel", "freecharge", "jupiteraxis", "fam",
        "naviaxis", "slice", "timecosmos", "waaxis", "rapl", "abfspay",
    }
)

_EMAIL_HOSTS = frozenset({"com", "in", "org", "net", "co"})


def extract_vpa(raw: str) -> str:
    """First counterparty VPA in the narration, lowercased, else "".

    An email address is not a VPA, so `.com`/`.in` hosts are skipped: a support
    address quoted in a narration must not become a merchant.
    """
    for match in _VPA_RE.finditer(raw):
        handle, host = match.group(1).lower(), match.group(2).lower()
        if "." in host and host.rsplit(".", 1)[-1] in _EMAIL_HOSTS:
            continue
        return handle + "@" + host
    return ""


def vpa_handle(vpa: str) -> str:
    """The merchant-identifying half of a VPA, or "" if it names only a PSP."""
    if "@" not in vpa:
        return ""
    handle = vpa.split("@", 1)[0].lower()
    return "" if handle in _PSP_HANDLES else handle


# --- Merchant ---------------------------------------------------------------

_REF_RUN_RE = re.compile(r"\d{6,}")
_CORPORATE_SUFFIX_RE = re.compile(
    r"\s*\b(PVT|PRIVATE|PUBLIC)?\s*\b(LTD|LIMITED|LLP|INC|CORP|CORPORATION)\b\.?\s*$",
    re.I,
)
#: Words describing the *transaction*, not the counterparty. "LIC INDIA PREMIUM"
#: and "LIC INDIA" are the same payee, and must land in the same series.
_TRAILING_NOISE_RE = re.compile(
    r"\s*\b(PREMIUM|AUTOPAY|PAYMENT|PAYMENTS|MANDATE|COLLECTION|COLLECT|"
    r"RECURRING|SUBSCRIPTION|BILLDESK|BILLPAY|RAZORPAY|RAZP|PAYU|CCAVENUE)\b\s*$",
    re.I,
)
_CITY_SUFFIXES = (
    "NAVI MUMBAI", "NEW DELHI", "BENGALURU", "BANGALORE", "MUMBAI", "DELHI",
    "CHENNAI", "HYDERABAD", "PUNE", "KOLKATA", "AHMEDABAD", "GURUGRAM",
    "GURGAON", "NOIDA", "JAIPUR", "KOCHI", "COIMBATORE", "INDORE", "LUCKNOW",
    "CHANDIGARH", "NAGPUR", "SURAT", "BHOPAL", "PATNA", "VISAKHAPATNAM",
    "THANE",
)

_UPI_FROM_RE = re.compile(r"UPI[/-][A-Z]{2}[/-]\d+[/-]([^/]+)[/-]", re.I)
_PAYMENT_TO_RE = re.compile(r"PAYMENT\s+TO\s+([^/]+)", re.I)
_EMANDATE_RE = re.compile(r"E-?MANDATE[/-]([^/]+)", re.I)
_ACH_RE = re.compile(r"\bACH\s*[DC]?-\s*(.+)$", re.I)
_SI_RE = re.compile(r"\bSI-\s*(.+)$", re.I)
_NEFT_RE = re.compile(r"\b(?:NEFT|IMPS|RTGS)\s+(?:CR|DR)-[A-Z0-9]+-([^-]+)", re.I)
_POS_RE = re.compile(r"\bPOS\s+\d+\s+(.+)$", re.I)
_ATM_RE = re.compile(r"\bATW\b|\bATM\b|\bNWD\b|CASH\s+WDL", re.I)
_INTEREST_RE = re.compile(r"INTEREST.*CAPITALISED|CREDIT\s+INTEREST", re.I)
_TRANSFER_WRAPPER_RE = re.compile(r"^(?:TO|BY)\s+TRANSFER\s*-\s*", re.I)


def _tidy(token: str) -> str:
    token = _REF_RUN_RE.sub(" ", token)
    token = re.sub(r"[^A-Za-z0-9&.\s-]", " ", token)
    token = re.sub(r"\s+", " ", token).strip(" -.")
    token = _CORPORATE_SUFFIX_RE.sub("", token).strip(" -.")
    token = _TRAILING_NOISE_RE.sub("", token).strip(" -.")
    upper = token.upper()
    for city in _CITY_SUFFIXES:
        if upper.endswith(" " + city):
            upper = upper[: -(len(city) + 1)].strip()
            break
    return upper


def extract_merchant(raw: str) -> str:
    """Best-effort counterparty name from a narration.

    Shapes are tried in order of how much structure they give us. ATM
    withdrawals deliberately collapse to a single name: the counterparty is the
    user's own cash, and keying on the branch would shatter one real habit into
    a dozen one-off merchants.
    """
    text = _TRANSFER_WRAPPER_RE.sub("", raw.strip())

    if _ATM_RE.search(text):
        return "ATM WITHDRAWAL"
    if _INTEREST_RE.search(text):
        return "INTEREST CREDIT"

    for pattern in (
        _EMANDATE_RE,
        _UPI_FROM_RE,
        _PAYMENT_TO_RE,
        _NEFT_RE,
        _ACH_RE,
        _SI_RE,
        _POS_RE,
    ):
        match = pattern.search(text)
        if match:
            candidate = _tidy(match.group(1))
            if candidate:
                return candidate

    handle = vpa_handle(extract_vpa(text))
    if handle:
        return handle.upper()
    return _tidy(text) or "UNKNOWN"


# --- Canonical form ---------------------------------------------------------

_CANONICAL_STRIP_RE = re.compile(r"\d{4,}")


def canonical_narration(raw: str) -> str:
    """Narration with volatile parts removed, for cache keys and grouping.

    Reference and transaction ids differ on every row of an otherwise identical
    series, so they collapse to a single placeholder.
    """
    text = _CANONICAL_STRIP_RE.sub("#", raw.upper())
    text = re.sub(r"[^A-Z0-9@#/.\s-]", " ", text)
    return re.sub(r"\s+", " ", text).strip(" -/")


# --- Result -----------------------------------------------------------------


@dataclass(frozen=True)
class NormalizedRow:
    txn_date: str  # ISO date; the adapter has already parsed it
    amount_paise: int
    direction: Direction
    raw_narration: str
    normalized_merchant: str
    counterparty_vpa: str
    channel: Channel
    canonical: str
    balance_paise: int | None = None


def normalize(
    *,
    txn_date: str,
    raw_narration: str,
    amount_paise: int,
    direction: Direction,
    balance_paise: int | None = None,
) -> NormalizedRow:
    return NormalizedRow(
        txn_date=txn_date,
        amount_paise=amount_paise,
        direction=direction,
        raw_narration=raw_narration,
        normalized_merchant=extract_merchant(raw_narration),
        counterparty_vpa=extract_vpa(raw_narration),
        channel=classify_channel(raw_narration),
        canonical=canonical_narration(raw_narration),
        balance_paise=balance_paise,
    )
