"""Tier-1 deterministic categorisation (DESIGN.md section 7).

Free, instant and auditable: every decision points at the rule that made it, so
a wrong category is a rule you can read and fix rather than a model you can
only re-prompt. The target is ~75% of retail transactions handled here, leaving
the tail to tier 2.

Rules are tried in descending priority:

  1000  user overrides (tier 3) — authoritative, never overridden by a guess
   900  VPA handle — chosen by the merchant, stable across banks
   800  merchant dictionary, exact token
   700  narration structure (ACH mandates, salary credits, ATM withdrawals)
   600  merchant dictionary, substring
   500  channel-derived fallback (a UPI debit to an unknown payee is still spend)

Confidence below 0.6 lands in `Uncategorised` rather than a guess, per
DESIGN.md section 7. Showing "Uncategorised" honestly is better than showing a
confident wrong answer; the latter is how PFM tools quietly lie.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..engine.types import UNCATEGORISED_SLUG, Channel, Direction
from ..ingest.normalize import vpa_handle
from .merchants import MerchantEntry, lookup

MIN_CONFIDENCE = 0.6


@dataclass(frozen=True)
class Classification:
    category_slug: str
    merchant: str
    confidence: float
    source: str  # "RULE" | "LLM" | "USER"
    rule: str  # which rule fired, for the audit trail
    service_type: str | None = None

    @property
    def is_confident(self) -> bool:
        return self.confidence >= MIN_CONFIDENCE


UNCATEGORISED = Classification(
    category_slug=UNCATEGORISED_SLUG,
    merchant="",
    confidence=0.0,
    source="RULE",
    rule="none",
)


@dataclass(frozen=True)
class UserRule:
    """A tier-3 override (DESIGN.md section 7). Priority 1000, scope USER."""

    pattern: str
    match_type: str  # "exact" | "contains" | "vpa"
    category_slug: str
    merchant: str = ""

    def matches(self, merchant_token: str, handle: str) -> bool:
        token = (merchant_token or "").upper()
        if self.match_type == "vpa":
            return bool(handle) and handle.lower() == self.pattern.lower()
        if self.match_type == "exact":
            return token == self.pattern.upper()
        return self.pattern.upper() in token


#: Narration-shape rules. These catch the payees a dictionary cannot know
#: because they are specific to one user: their landlord, their employer, their
#: loan account.
_STRUCTURAL_RULES: tuple[tuple[str, re.Pattern[str], str, float], ...] = (
    ("salary-credit", re.compile(r"\bSALARY\b|\bSAL\s+CR\b|\bPAYROLL\b", re.I), "salary", 0.95),
    ("home-loan", re.compile(r"\bHOME\s*LOAN\b|\bHOUSING\s*LOAN\b", re.I), "emi-loan-repayment", 0.95),
    ("vehicle-loan", re.compile(r"\b(CAR|AUTO|TWO\s*WHEELER|VEHICLE)\s*LOAN\b", re.I), "emi-loan-repayment", 0.95),
    ("personal-loan", re.compile(r"\bPERSONAL\s*LOAN\b|\bLOAN\s*EMI\b|\bEMI\b", re.I), "emi-loan-repayment", 0.85),
    ("rent-mandate", re.compile(r"\bLANDLORD\b|\bHOUSE\s*RENT\b|\bRENT\b", re.I), "rent", 0.85),
    ("maintenance", re.compile(r"\b(SOCIETY|FLAT|APARTMENT)\s*MAINTENANCE\b|\bMAINTENANCE\s*CHARGE", re.I), "rent", 0.80),
    ("credit-card-bill", re.compile(r"\bCREDIT\s*CARD\b|\bCARD\s*PAYMENT\b|\bCC\s*PAYMENT\b", re.I), "credit-card-payment", 0.85),
    ("atm", re.compile(r"\bATW\b|\bATM\b|\bNWD\b|CASH\s+WDL", re.I), "cash-withdrawal", 0.95),
    ("interest", re.compile(r"INTEREST.*CAPITALISED|CREDIT\s+INTEREST|\bINT\.?\s*CR\b", re.I), "interest", 0.90),
    ("self-transfer", re.compile(r"SELF\s*TRANSFER|\bOWN\s*ACCOUNT\b", re.I), "transfer-out", 0.85),
    ("bank-charges", re.compile(r"\b(SMS|AMC|ANNUAL)\s*(CHARGE|FEE)|\bGST\b.*CHARGE|SERVICE\s*CHARGE|\bPENALTY\b", re.I), "fees-charges", 0.85),
    ("mutual-fund", re.compile(r"\bMUTUAL\s*FUND\b|\bSIP\b|\bMF\s*PURCHASE\b", re.I), "investment-sip", 0.85),
    ("insurance", re.compile(r"\bINSURANCE\b|\bPREMIUM\b|\bPOLICY\b", re.I), "insurance-premium", 0.80),
    ("refund", re.compile(r"\bREFUND\b|\bREVERSAL\b|\bCASHBACK\b", re.I), "refund", 0.85),
)

#: Last resort before Uncategorised. A transfer we cannot name is still a
#: transfer, and saying so beats a blank.
_CHANNEL_FALLBACK: dict[Channel, tuple[str, float]] = {
    Channel.ATM: ("cash-withdrawal", 0.85),
    Channel.CASH: ("cash-withdrawal", 0.70),
}


def classify(
    *,
    normalized_merchant: str,
    raw_narration: str,
    counterparty_vpa: str = "",
    channel: Channel = Channel.OTHER,
    direction: Direction = Direction.DEBIT,
    user_rules: tuple[UserRule, ...] = (),
) -> Classification:
    """Tier-1 classification, or `UNCATEGORISED` if nothing is confident."""
    handle = vpa_handle(counterparty_vpa)

    for rule in user_rules:
        if rule.matches(normalized_merchant, handle):
            return Classification(
                category_slug=rule.category_slug,
                merchant=rule.merchant or normalized_merchant,
                confidence=1.0,
                source="USER",
                rule="user-override",
            )

    if handle:
        hit = lookup("", handle)
        if hit:
            return _from_entry(hit, 0.95, "vpa")

    hit = lookup(normalized_merchant)
    if hit and hit.match_type == "exact":
        return _from_entry(hit, 0.90, "dictionary-exact")

    for name, pattern, slug, confidence in _STRUCTURAL_RULES:
        if pattern.search(raw_narration):
            return Classification(
                category_slug=slug,
                merchant=normalized_merchant,
                confidence=confidence,
                source="RULE",
                rule=name,
            )

    if hit:
        return _from_entry(hit, 0.75, "dictionary-" + hit.match_type)

    fallback = _CHANNEL_FALLBACK.get(channel)
    if fallback:
        slug, confidence = fallback
        return Classification(
            category_slug=slug,
            merchant=normalized_merchant,
            confidence=confidence,
            source="RULE",
            rule="channel-fallback",
        )

    return UNCATEGORISED


def _from_entry(entry: MerchantEntry, confidence: float, rule: str) -> Classification:
    return Classification(
        category_slug=entry.category_slug,
        merchant=entry.merchant,
        confidence=confidence,
        source="RULE",
        rule=rule,
        service_type=entry.service_type,
    )
