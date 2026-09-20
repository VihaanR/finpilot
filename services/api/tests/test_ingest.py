"""T04 — ingestion: normalisation, adapters, dedupe, the pipeline."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.engine.types import Channel, Direction
from app.ingest.adapters.base import ParseError, RawRow
from app.ingest.adapters.bank_pdf import HdfcPdfAdapter, IciciPdfAdapter
from app.ingest.adapters.generic_csv import GenericCsvAdapter
from app.ingest.adapters.llm_fallback import LlmFallbackAdapter
from app.ingest.banks import detect_bank, hint_for
from app.ingest.dedupe import dedupe_key, normalize_for_dedupe, partition_new
from app.ingest.normalize import (
    canonical_narration,
    classify_channel,
    extract_merchant,
    extract_vpa,
    normalize,
    to_paise,
    vpa_handle,
)
from app.ingest.registry import parse as registry_parse
from app.store.db import Store

SEED_OUTPUT = Path(__file__).resolve().parents[3] / "seed" / "output"


# --- Money ------------------------------------------------------------------


def test_to_paise_is_exact_on_values_float_would_round_wrong():
    # int(1725.55 * 100) is 172554 in binary floating point.
    assert to_paise("1725.55") == 172555
    assert to_paise("0.01") == 1
    assert to_paise("110000.00") == 11000000
    assert to_paise("1,23,456.78") == 12345678


def test_to_paise_rejects_float_rather_than_coercing():
    with pytest.raises(TypeError):
        to_paise(1725.55)


def test_to_paise_rejects_non_amounts():
    with pytest.raises(ValueError):
        to_paise("not a number")


# --- Narration --------------------------------------------------------------


@pytest.mark.parametrize(
    "narration,expected",
    [
        ("UPI/DR/596575692459/BLINKIT/OKAXIS/Payment from ph", "BLINKIT"),
        ("UPI/179904210202/Payment to THIRDWAVE/thirdwave@ybl/ICIC", "THIRDWAVE"),
        ("E-MANDATE/NETFLIX/AUTOPAY/181883552312", "NETFLIX"),
        ("ACH D- HDFC CAR LOAN 731781080132", "HDFC CAR LOAN"),
        ("SI- LIC INDIA PREMIUM 735158506431", "LIC INDIA"),
        ("NEFT CR-ACME0000191-ACME TECHNOLOGIES PVT LTD-SALARY-104332181960", "ACME TECHNOLOGIES"),
        ("POS 5563 CROMA BENGALURU", "CROMA"),
        ("TO TRANSFER-UPI/DR/323651994101/SELF TRANSFER/OKHDFCBANK/self@okhdfcbank--", "SELF TRANSFER"),
    ],
)
def test_extract_merchant_handles_indian_narration_shapes(narration, expected):
    assert extract_merchant(narration) == expected


def test_atm_withdrawals_collapse_to_one_merchant():
    # Keying on the branch would shatter one habit into many one-off merchants.
    assert extract_merchant("ATW-5896-INDIRANAGAR") == "ATM WITHDRAWAL"
    assert extract_merchant("ATW-2010-KORAMANGALA") == "ATM WITHDRAWAL"


@pytest.mark.parametrize(
    "narration,channel",
    [
        ("E-MANDATE/NETFLIX/AUTOPAY/1818", Channel.CARD),
        ("UPI/DR/5965/BLINKIT/OKAXIS/Payment", Channel.UPI),
        ("ACH D- HDFC CAR LOAN 7317", Channel.NACH),
        ("NEFT CR-ACME0000191-ACME-SALARY-1043", Channel.NEFT),
        ("ATW-5896-INDIRANAGAR", Channel.ATM),
        ("POS 5563 CROMA BENGALURU", Channel.CARD),
    ],
)
def test_classify_channel(narration, channel):
    assert classify_channel(narration) == channel


def test_extract_vpa_ignores_email_addresses():
    assert extract_vpa("UPI/1799/Payment to X/thirdwave@ybl/ICIC") == "thirdwave@ybl"
    assert extract_vpa("query to support@hdfcbank.com about charges") == ""


def test_vpa_handle_drops_psp_only_handles():
    assert vpa_handle("swiggy@ybl") == "swiggy"
    # "okhdfcbank" names the bank, not the payee.
    assert vpa_handle("okhdfcbank@okhdfcbank") == ""


def test_canonical_narration_collapses_reference_numbers():
    a = canonical_narration("E-MANDATE/NETFLIX/AUTOPAY/181883552312")
    b = canonical_narration("E-MANDATE/NETFLIX/AUTOPAY/970213556909")
    assert a == b  # one cache entry per narration shape, not per transaction


# --- Dedupe -----------------------------------------------------------------


def test_dedupe_normalisation_keeps_digits():
    # The reference number is the strongest per-transaction discriminator;
    # dropping it would merge two identical same-day purchases.
    a = normalize_for_dedupe("UPI/DR/111/BIGBASKET/YBL")
    b = normalize_for_dedupe("UPI/DR/222/BIGBASKET/YBL")
    assert a != b


def test_dedupe_key_is_stable_across_whitespace_and_case():
    base = dict(account_id="acc", txn_date="2026-09-19", amount_paise=124900)
    assert dedupe_key(**base, raw_narration="UPI/DR/1/BIGBASKET") == dedupe_key(
        **base, raw_narration="upi/dr/1/bigbasket  "
    )


def test_dedupe_key_changes_with_amount():
    base = dict(account_id="acc", txn_date="2026-09-19", raw_narration="X")
    assert dedupe_key(**base, amount_paise=100) != dedupe_key(**base, amount_paise=200)


def test_partition_new_dedupes_within_the_batch_too():
    keep, report = partition_new(["a", "b", "a", "c"], set())
    assert keep == [0, 1, 3]
    assert (report.total, report.inserted, report.duplicates) == (4, 3, 1)


# --- Adapters ---------------------------------------------------------------


def _seed_csv(name: str) -> str:
    return (SEED_OUTPUT / (name + ".csv")).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ["hdfc_savings", "icici_credit", "sbi_savings"])
def test_generic_csv_parses_every_seed_statement(seeded_store, name):
    adapter = GenericCsvAdapter()
    text = _seed_csv(name)
    assert adapter.detect(text, name + ".csv") >= 0.9
    rows = adapter.parse(text)
    assert rows and all(isinstance(r, RawRow) for r in rows)
    assert all(r.amount_paise > 0 for r in rows)


def test_generic_csv_reads_indian_dates_day_first(seeded_store):
    rows = GenericCsvAdapter().parse(_seed_csv("hdfc_savings"))
    # 01/08/2025 is 1 August, not 8 January.
    assert rows[0].txn_date == date(2025, 8, 1)


def test_generic_csv_handles_single_signed_amount_column():
    text = "Date,Description,Amount\n19/09/2026,UPI/DR/1/SWIGGY/YBL,-450.50\n19/09/2026,SALARY,1000.00\n"
    rows = GenericCsvAdapter().parse(text)
    assert len(rows) == 2
    assert rows[0].amount_paise == 45050 and rows[0].is_credit is False
    assert rows[1].is_credit is True


def test_generic_csv_handles_a_drcr_indicator_column():
    text = "Date,Particulars,Amount,Type\n19/09/2026,SOMETHING,450.50,DR\n19/09/2026,OTHER,10.00,CR\n"
    rows = GenericCsvAdapter().parse(text)
    assert rows[0].is_credit is False and rows[1].is_credit is True


def test_generic_csv_skips_preamble_rows_before_the_header():
    text = (
        "Statement of account\nAccount: XXXX4821\n\n"
        "Date,Narration,Withdrawal,Deposit\n19/09/2026,UPI/DR/1/SWIGGY/YBL,450.50,\n"
    )
    rows = GenericCsvAdapter().parse(text)
    assert len(rows) == 1 and rows[0].amount_paise == 45050


def test_malformed_input_raises_parse_error_not_a_crash():
    with pytest.raises(ParseError):
        GenericCsvAdapter().parse("this is not a statement at all")


def test_bank_pdf_adapters_decline_documents_that_are_not_theirs():
    assert HdfcPdfAdapter().detect("ICICI BANK statement", "x.pdf") == 0.0
    assert IciciPdfAdapter().detect("HDFC BANK statement", "x.pdf") == 0.0


def test_hdfc_pdf_adapter_parses_a_line_layout():
    text = (
        "HDFC BANK LTD\nStatement of Accounts\n"
        "01/08/2025 NEFT CR-ACME-SALARY-104332 110000.00 295000.00\n"
        "02/08/2025 UPI/DR/8486/UBER/YBL/Payment 293.00 294707.00\n"
    )
    adapter = HdfcPdfAdapter()
    assert adapter.detect(text, "stmt.pdf") > 0.5
    rows = adapter.parse(text)
    assert len(rows) == 2
    assert rows[0].is_credit is True and rows[0].amount_paise == 11000000
    assert rows[1].is_credit is False and rows[1].amount_paise == 29300


def test_llm_fallback_declines_cleanly_without_an_api_key():
    adapter = LlmFallbackAdapter()
    if adapter.available:  # a key is configured in this environment
        return
    assert adapter.detect("anything", "x.csv") == 0.0
    with pytest.raises(ParseError) as exc:
        adapter.parse("anything")
    assert exc.value.code == "LLM_UNAVAILABLE"


def test_registry_picks_the_most_confident_adapter():
    outcome = registry_parse(_seed_csv("hdfc_savings"), "hdfc_savings.csv")
    assert outcome.adapter_name == "generic_csv"
    assert outcome.confidence >= 0.9
    assert outcome.is_low_confidence is False


def test_registry_reports_no_adapter_for_unrecognisable_input():
    with pytest.raises(ParseError):
        registry_parse("", "mystery.bin")


# --- Banks ------------------------------------------------------------------


def test_bank_detection_and_hints():
    assert detect_bank("HDFC BANK LTD statement", "") == "HDFC"
    assert hint_for("HDFC").formats == ("Your Customer ID",)
    # SBI genuinely has three formats depending on where the file came from.
    assert len(hint_for("SBI").formats) == 3
    assert hint_for(None).bank_code == "UNKNOWN"


# --- Pipeline ---------------------------------------------------------------


def test_ingesting_the_seed_produces_the_expected_transaction_count(seeded_store):
    assert seeded_store.transaction_count() == 936


def test_uploading_the_same_file_twice_inserts_nothing(seeded_store):
    """The critical T04 criterion."""
    from app.ingest.pipeline import ingest

    before = seeded_store.transaction_count()
    account_id = seeded_store.accounts()[0]["id"]
    path = SEED_OUTPUT / "hdfc_savings.csv"

    result = ingest(
        seeded_store, data=path.read_bytes(), filename=path.name, account_id=account_id
    )

    assert result.inserted == 0
    assert result.duplicates == 669
    assert seeded_store.transaction_count() == before


def test_ingest_records_which_adapter_read_the_document(seeded_store):
    documents = seeded_store.documents()
    assert documents
    assert all(d["adapter_name"] == "generic_csv" for d in documents)
    assert all(d["confidence"] >= 0.9 for d in documents)


def test_every_stored_amount_is_int_paise(seeded_store):
    for row in seeded_store.transactions(limit=1000):
        assert isinstance(row["amount_paise"], int)
        assert row["amount_paise"] > 0


def test_ingest_of_a_malformed_file_reports_an_error_event():
    from app.ingest.pipeline import run

    store = Store(":memory:")
    events = list(run(store, data=b"garbage not a statement", filename="x.csv"))
    assert events[-1]["stage"] == "done"
    assert events[-1]["ok"] is False
    assert any(e["stage"] == "error" for e in events)
    store.close()


def test_normalize_end_to_end_produces_engine_ready_rows():
    row = normalize(
        txn_date="2026-09-19",
        raw_narration="UPI/DR/596575692459/BLINKIT/OKAXIS/Payment from ph",
        amount_paise=55500,
        direction=Direction.DEBIT,
    )
    assert row.normalized_merchant == "BLINKIT"
    assert row.channel == Channel.UPI
    assert row.amount_paise == 55500
