"""HDFC email-alert adapter and the Gmail sync ingest path.

`_SAMPLE_TEXT` is the plain-text body of a real HDFC InstaAlert email, after
HTML stripping — the same shape `ingest/gmail.py::_extract_text` produces.
"""

from __future__ import annotations

from datetime import date

from app.ingest.adapters.hdfc_email import HdfcEmailAdapter
from app.ingest.pipeline import ingest_parsed_rows
from app.store.db import Store

_SAMPLE_TEXT = (
    "Dear Customer, Greetings from HDFC Bank! Rs.20.00 is debited from your "
    "account ending 5856 towards VPA mmmocl.zkp@icici (Maha Mumbai Metro "
    "Operation Corporation Limited) on 17-09-26. UPI transaction reference "
    "no.: 129747863195. If you did not authorize this transaction, please "
    "report it immediately at: a. When in India (Toll free): 1800 258 6161 "
    "Warm regards, HDFC Bank"
)

_UNRELATED_TEXT = "Your OTP for login is 482913. Do not share it with anyone."


def test_detect_scores_zero_for_non_hdfc_text():
    assert HdfcEmailAdapter().detect(_UNRELATED_TEXT, "gmail:1.txt") == 0.0


def test_detect_scores_high_for_a_real_alert():
    assert HdfcEmailAdapter().detect(_SAMPLE_TEXT, "gmail:1.txt") >= 0.9


def test_parse_extracts_the_one_row():
    rows = HdfcEmailAdapter().parse(_SAMPLE_TEXT)
    assert len(rows) == 1
    row = rows[0]
    assert row.txn_date == date(2026, 9, 17)
    assert row.amount_paise == 2000
    assert row.is_credit is False
    assert "129747863195" in row.raw_narration
    assert "mmmocl.zkp@icici" in row.raw_narration
    assert "MAHA MUMBAI METRO" in row.raw_narration


def test_parse_returns_nothing_for_an_email_that_does_not_match():
    """A different HDFC alert type is skipped, never guessed at."""
    other_hdfc_text = "Greetings from HDFC Bank! Your OTP is 123456."
    assert HdfcEmailAdapter().parse(other_hdfc_text) == []


def test_ingest_parsed_rows_inserts_one_transaction():
    store = Store(":memory:")
    rows = HdfcEmailAdapter().parse(_SAMPLE_TEXT)

    result = ingest_parsed_rows(
        store,
        rows=rows,
        adapter_name="hdfc_email_alert",
        adapter_version="1.0.0",
        confidence=0.9,
        filename="gmail:msg1.txt",
        bank_code="HDFC",
        account_name="HDFC Bank — Email Alerts",
    )

    assert result.inserted == 1
    assert result.duplicates == 0
    assert store.transaction_count() == 1
    txn = store.transactions()[0]
    assert txn["amount_paise"] == 2000
    assert txn["direction"] == "DEBIT"
    store.close()


def test_ingest_parsed_rows_dedupes_the_same_email_synced_twice():
    store = Store(":memory:")
    rows = HdfcEmailAdapter().parse(_SAMPLE_TEXT)
    kwargs = dict(
        rows=rows,
        adapter_name="hdfc_email_alert",
        adapter_version="1.0.0",
        confidence=0.9,
        filename="gmail:msg1.txt",
        bank_code="HDFC",
        account_name="HDFC Bank — Email Alerts",
    )
    ingest_parsed_rows(store, **kwargs)
    second = ingest_parsed_rows(store, **kwargs)

    assert second.inserted == 0
    assert second.duplicates == 1
    assert store.transaction_count() == 1
    store.close()


def test_ingest_parsed_rows_is_a_noop_for_an_empty_row_list():
    store = Store(":memory:")
    result = ingest_parsed_rows(
        store,
        rows=[],
        adapter_name="hdfc_email_alert",
        adapter_version="1.0.0",
        confidence=0.0,
        filename="gmail:msg2.txt",
        bank_code="HDFC",
    )
    assert result.parsed == 0
    assert result.inserted == 0
    assert store.transaction_count() == 0
    store.close()
