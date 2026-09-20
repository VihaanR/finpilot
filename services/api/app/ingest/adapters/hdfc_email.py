"""HDFC UPI InstaAlert email adapter (DESIGN.md 6.1, extended for Gmail sync).

One HDFC InstaAlert email carries exactly one UPI transaction. `ingest/gmail.py`
strips such an email down to plain text and hands it through the same
sniff -> detect -> parse flow as an uploaded PDF or CSV (`ingest/pipeline.py`),
so one alert becomes one `RawRow` here, then flows through the ordinary
normalise -> classify -> dedupe -> insert steps unchanged.

Built and verified against one real (redacted) alert:

    Rs.20.00 is debited from your account ending 5856 towards VPA
    mmmocl.zkp@icici (Maha Mumbai Metro Operation Corporation Limited) on
    17-09-26. UPI transaction reference no.: 129747863195.

Only this template is handled. A credited-side alert, a different HDFC
notification type, or a future wording change simply does not match
`_ALERT_RE` and scores 0.0 confidence — the registry then reports
`NO_ADAPTER`/`NO_ROWS_PARSED` rather than this adapter guessing at a shape
it has never seen for real.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from ..normalize import to_paise
from .base import RawRow

_ALERT_RE = re.compile(
    r"Rs\.?\s*(?P<amount>[\d,]+\.\d{2})\s+is\s+(?P<direction>debited|credited)\s+"
    r"(?:from|to)\s+your\s+account\s+ending\s*(?P<last4>\d+)\s+towards\s+VPA\s+"
    r"(?P<vpa>[\w.\-]+@[\w.\-]+)\s*\((?P<merchant>[^)]+)\)\s+on\s+"
    r"(?P<date>\d{2}-\d{2}-\d{2})",
    re.I,
)
_REF_RE = re.compile(r"reference\s+no\.?:?\s*(?P<ref>\d+)", re.I)


def _parse_alert_date(text: str) -> date:
    return datetime.strptime(text, "%d-%m-%y").date()


class HdfcEmailAdapter:
    name = "hdfc_email_alert"
    version = "1.0.0"

    def detect(self, text: str, filename: str) -> float:
        if "HDFC BANK" not in text.upper():
            return 0.0
        return 0.9 if _ALERT_RE.search(text) else 0.0

    def parse(self, text: str) -> list[RawRow]:
        match = _ALERT_RE.search(text)
        if not match:
            return []
        ref_match = _REF_RE.search(text)
        ref = ref_match.group("ref") if ref_match else "0"
        merchant = re.sub(r"\s+", " ", match.group("merchant")).strip().upper()
        vpa = match.group("vpa").strip().lower()
        is_credit = match.group("direction").lower() == "credited"
        direction_code = "CR" if is_credit else "DR"
        # Shaped like a statement's own UPI narration ("UPI/DR/<ref>/<merchant>/
        # <vpa>") so the existing merchant/VPA extraction in normalize.py reads
        # it exactly as it would a PDF or CSV row, with no email-specific logic
        # downstream of this adapter.
        narration = "UPI/{0}/{1}/{2}/{3}".format(direction_code, ref, merchant, vpa)
        return [
            RawRow(
                txn_date=_parse_alert_date(match.group("date")),
                raw_narration=narration,
                amount_paise=to_paise(match.group("amount")),
                is_credit=is_credit,
            )
        ]
