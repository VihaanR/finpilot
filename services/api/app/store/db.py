"""Local persistence.

The Supabase schema in `supabase/migrations/` is the production target, but no
project exists yet and the migrations have never been run (see PROGRESS.md).
Rather than block every other task on one external signup, this module keeps
the same shapes in SQLite so ingestion, the API and the whole frontend work
offline. When Supabase lands at T12 this becomes the second implementation of
one interface, not a rewrite.

Deliberately not SQLAlchemy: `app/models/tables.py` is written against Postgres
types (UUID, JSONB) and bending it to SQLite would compromise the production
models for the sake of the local one. Raw SQL over a schema that mirrors the
migration is smaller and keeps the Postgres models pristine.

Money is INTEGER paise. SQLite stores integers up to 8 bytes, so BIGINT paise
survives exactly.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from ..engine.types import Budget, Channel, Direction, Goal, Txn
from ..ingest.dedupe import dedupe_key, partition_new
from ..ingest.normalize import NormalizedRow

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "finpilot.db"

_SCHEMA = """
create table if not exists accounts (
  id text primary key,
  bank_code text not null,
  account_type text not null default 'SAVINGS',
  display_name text not null,
  last4 text,
  opening_balance_paise integer not null default 0,
  current_balance_paise integer not null default 0,
  balance_as_of text
);

create table if not exists documents (
  id text primary key,
  filename text not null,
  bank_code text,
  adapter_name text,
  adapter_version text,
  confidence real,
  status text not null default 'PARSED',
  row_count integer not null default 0,
  inserted_count integer not null default 0,
  duplicate_count integer not null default 0,
  created_at text not null
);

create table if not exists transactions (
  id text primary key,
  account_id text not null references accounts(id) on delete cascade,
  document_id text references documents(id) on delete set null,
  txn_date text not null,
  amount_paise integer not null,
  direction text not null,
  raw_narration text not null,
  normalized_merchant text not null,
  counterparty_vpa text not null default '',
  channel text not null default 'OTHER',
  category_slug text not null default 'uncategorised',
  category_source text not null default 'RULE',
  category_confidence real not null default 0.0,
  service_type text,
  balance_paise integer,
  dedupe_key text not null unique
);

create index if not exists ix_txn_date on transactions(txn_date);
create index if not exists ix_txn_merchant on transactions(normalized_merchant);
create index if not exists ix_txn_category on transactions(category_slug);

create table if not exists merchant_rules (
  id text primary key,
  pattern text not null,
  match_type text not null,
  merchant text not null default '',
  category_slug text not null,
  priority integer not null default 1000,
  scope text not null default 'USER',
  created_at text not null
);

create table if not exists goals (
  id text primary key,
  name text not null,
  target_paise integer not null,
  current_paise integer not null default 0,
  target_date text not null,
  priority integer not null default 0,
  monthly_contribution_paise integer not null default 0
);

create table if not exists budgets (
  category_slug text primary key,
  limit_paise integer not null,
  period_start text not null
);

create table if not exists acknowledgements (
  series_key text primary key,
  acknowledged_at text not null
);

create table if not exists dismissals (
  anomaly_key text primary key,
  dismissed_at text not null
);

-- Soft delete, as a side table rather than a column on `transactions`.
-- Same shape as `dismissals` above, and for the same reasons: the ledger
-- rows stay byte-identical to what was ingested, and a removal is undone by
-- deleting one row rather than by rewriting history.
create table if not exists deleted_transactions (
  txn_id text primary key,
  deleted_at text not null,
  reason text
);

-- What the Budget Guard extension actually stopped, reported back from the
-- browser. Before this the extension was a dead end: it intercepted a
-- checkout and the web app never knew, so the two halves of the product had
-- no shared memory of the same event.
create table if not exists guard_events (
  id text primary key,
  created_at text not null,
  site text not null,
  outcome text not null,
  cart_paise integer not null default 0,
  discretionary_paise integer not null default 0
);

create table if not exists ai_disclosures (
  id text primary key,
  created_at text not null,
  purpose text not null,
  model text not null,
  provider text not null default 'Google Gemini',
  field_types text not null default '[]',
  redacted_count integer not null default 0
);

create table if not exists consents (
  id text primary key,
  created_at text not null,
  version text not null,
  scope text not null,
  granted integer not null default 1
);

-- Single stored Gmail connection (USER-facing "Connect Gmail" vault panel).
-- Not in `_USER_TABLES`: `refresh_token` must never appear in the DPDP export
-- bundle, so erase/export/inventory handle this table explicitly instead of
-- through the generic loop.
create table if not exists email_connections (
  id text primary key,
  provider text not null default 'gmail',
  email_address text not null,
  refresh_token text not null,
  last_synced_at text,
  last_message_internal_date text,
  created_at text not null
);
"""

_USER_TABLES = (
    "transactions", "documents", "accounts", "goals", "budgets",
    "merchant_rules", "acknowledgements", "dismissals", "deleted_transactions",
    "guard_events", "ai_disclosures", "consents",
)


def _new_id() -> str:
    return uuid.uuid4().hex


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_DB_PATH
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("pragma foreign_keys = on")
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # --- Accounts -----------------------------------------------------------

    def upsert_account(
        self,
        *,
        account_id: str | None = None,
        bank_code: str,
        display_name: str,
        account_type: str = "SAVINGS",
        last4: str | None = None,
        opening_balance_paise: int = 0,
    ) -> str:
        existing = self.conn.execute(
            "select id from accounts where display_name = ?", (display_name,)
        ).fetchone()
        if existing:
            return str(existing["id"])
        new = account_id or _new_id()
        self.conn.execute(
            "insert into accounts (id, bank_code, account_type, display_name, last4,"
            " opening_balance_paise, current_balance_paise) values (?,?,?,?,?,?,?)",
            (new, bank_code, account_type, display_name, last4,
             opening_balance_paise, opening_balance_paise),
        )
        self.conn.commit()
        return new

    def accounts(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("select * from accounts order by display_name").fetchall()
        return [dict(r) for r in rows]

    # --- Documents ----------------------------------------------------------

    def record_document(
        self,
        *,
        filename: str,
        bank_code: str | None,
        adapter_name: str,
        adapter_version: str,
        confidence: float,
        row_count: int,
        inserted_count: int,
        duplicate_count: int,
        status: str = "PARSED",
    ) -> str:
        doc_id = _new_id()
        self.conn.execute(
            "insert into documents (id, filename, bank_code, adapter_name,"
            " adapter_version, confidence, status, row_count, inserted_count,"
            " duplicate_count, created_at) values (?,?,?,?,?,?,?,?,?,?,?)",
            (doc_id, filename, bank_code, adapter_name, adapter_version,
             confidence, status, row_count, inserted_count, duplicate_count, _now()),
        )
        self.conn.commit()
        return doc_id

    def document(self, doc_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("select * from documents where id = ?", (doc_id,)).fetchone()
        return dict(row) if row else None

    def documents(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("select * from documents order by created_at desc").fetchall()
        return [dict(r) for r in rows]

    # --- Transactions -------------------------------------------------------

    def existing_keys(self) -> set[str]:
        return {
            str(r["dedupe_key"])
            for r in self.conn.execute("select dedupe_key from transactions").fetchall()
        }

    def insert_transactions(
        self,
        *,
        account_id: str,
        document_id: str | None,
        rows: list[tuple[NormalizedRow, str, str, float, str | None]],
    ) -> tuple[int, int]:
        """Insert normalised+classified rows, skipping duplicates.

        `rows` carries (normalized, category_slug, source, confidence, service_type).
        Returns (inserted, duplicates).
        """
        keys = [
            dedupe_key(
                account_id=account_id,
                txn_date=normalized.txn_date,
                amount_paise=normalized.amount_paise,
                raw_narration=normalized.raw_narration,
            )
            for normalized, _, _, _, _ in rows
        ]
        keep, report = partition_new(keys, self.existing_keys())

        payload = []
        for index in keep:
            normalized, slug, source, confidence, service_type = rows[index]
            payload.append(
                (
                    _new_id(), account_id, document_id, normalized.txn_date,
                    normalized.amount_paise, normalized.direction.value,
                    normalized.raw_narration, normalized.normalized_merchant,
                    normalized.counterparty_vpa, normalized.channel.value,
                    slug, source, confidence, service_type,
                    normalized.balance_paise, keys[index],
                )
            )
        if payload:
            self.conn.executemany(
                "insert or ignore into transactions (id, account_id, document_id,"
                " txn_date, amount_paise, direction, raw_narration,"
                " normalized_merchant, counterparty_vpa, channel, category_slug,"
                " category_source, category_confidence, service_type, balance_paise,"
                " dedupe_key) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                payload,
            )
            self._refresh_balance(account_id)
        self.conn.commit()
        return report.inserted, report.duplicates

    def _refresh_balance(self, account_id: str) -> None:
        row = self.conn.execute(
            "select balance_paise, txn_date from transactions"
            " where account_id = ? and balance_paise is not null"
            " order by txn_date desc, rowid desc limit 1",
            (account_id,),
        ).fetchone()
        if row:
            self.conn.execute(
                "update accounts set current_balance_paise = ?, balance_as_of = ?"
                " where id = ?",
                (row["balance_paise"], row["txn_date"], account_id),
            )

    def transactions(
        self,
        *,
        limit: int | None = None,
        offset: int = 0,
        category_slug: str | None = None,
        search: str | None = None,
        since: str | None = None,
        ids: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        sql = (
            "select * from transactions "
            "where id not in (select txn_id from deleted_transactions)"
        )
        args: list[Any] = []
        if ids is not None:
            if not ids:
                return []
            sql += " and id in ({0})".format(",".join("?" * len(ids)))
            args += list(ids)
        if category_slug:
            sql += " and category_slug = ?"
            args.append(category_slug)
        if since:
            sql += " and txn_date >= ?"
            args.append(since)
        if search:
            sql += " and (normalized_merchant like ? or raw_narration like ?)"
            args += ["%" + search.upper() + "%", "%" + search + "%"]
        sql += " order by txn_date desc, rowid desc"
        if limit is not None:
            sql += " limit ? offset ?"
            args += [limit, offset]
        return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def transaction_count(self) -> int:
        return int(self.conn.execute("select count(*) c from transactions").fetchone()["c"])

    def engine_txns(self) -> tuple[Txn, ...]:
        """Stored rows adapted into the engine's frozen dataclasses."""
        out: list[Txn] = []
        for row in self.conn.execute(
            "select * from transactions "
            "where id not in (select txn_id from deleted_transactions) "
            "order by txn_date"
        ).fetchall():
            out.append(
                Txn(
                    id=str(row["id"]),
                    txn_date=date.fromisoformat(str(row["txn_date"])),
                    amount_paise=int(row["amount_paise"]),
                    direction=Direction(str(row["direction"])),
                    raw_narration=str(row["raw_narration"]),
                    normalized_merchant=str(row["normalized_merchant"]),
                    category_slug=str(row["category_slug"]),
                    channel=Channel(str(row["channel"])),
                    account_id=str(row["account_id"]),
                    service_type=row["service_type"] or None,
                )
            )
        return tuple(out)

    # --- Category override (tier 3) ----------------------------------------

    def override_category(self, txn_id: str, category_slug: str) -> tuple[int, str]:
        """Apply a user override and back-fill matching history.

        Returns (rows updated, merchant). The retroactive update is the whole
        point: DESIGN.md section 7 tier 3 says one correction teaches the
        product, and the UI reports the count back as "Learned — N updated".
        """
        row = self.conn.execute(
            "select normalized_merchant from transactions where id = ?", (txn_id,)
        ).fetchone()
        if row is None:
            raise KeyError(txn_id)
        merchant = str(row["normalized_merchant"])

        self.conn.execute(
            "insert into merchant_rules (id, pattern, match_type, merchant,"
            " category_slug, priority, scope, created_at) values (?,?,?,?,?,?,?,?)",
            (_new_id(), merchant, "exact", merchant, category_slug, 1000, "USER", _now()),
        )
        cursor = self.conn.execute(
            "update transactions set category_slug = ?, category_source = 'USER',"
            " category_confidence = 1.0 where normalized_merchant = ?",
            (category_slug, merchant),
        )
        self.conn.commit()
        return cursor.rowcount, merchant

    def user_rules(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "select * from merchant_rules where scope = 'USER' order by created_at desc"
        ).fetchall()
        return [dict(r) for r in rows]

    # --- Goals and budgets --------------------------------------------------

    def upsert_goal(
        self,
        *,
        goal_id: str | None = None,
        name: str,
        target_paise: int,
        current_paise: int,
        target_date: str,
        priority: int = 0,
        monthly_contribution_paise: int = 0,
    ) -> str:
        new = goal_id or _new_id()
        self.conn.execute(
            "insert or replace into goals (id, name, target_paise, current_paise,"
            " target_date, priority, monthly_contribution_paise) values (?,?,?,?,?,?,?)",
            (new, name, target_paise, current_paise, target_date, priority,
             monthly_contribution_paise),
        )
        self.conn.commit()
        return new

    def goals(self) -> tuple[Goal, ...]:
        rows = self.conn.execute("select * from goals order by priority").fetchall()
        return tuple(
            Goal(
                id=str(r["id"]),
                name=str(r["name"]),
                target_paise=int(r["target_paise"]),
                current_paise=int(r["current_paise"]),
                target_date=date.fromisoformat(str(r["target_date"])),
                priority=int(r["priority"]),
                monthly_contribution_paise=int(r["monthly_contribution_paise"]),
            )
            for r in rows
        )

    def upsert_budget(self, *, category_slug: str, limit_paise: int, period_start: str) -> None:
        self.conn.execute(
            "insert or replace into budgets (category_slug, limit_paise, period_start)"
            " values (?,?,?)",
            (category_slug, limit_paise, period_start),
        )
        self.conn.commit()

    def budgets(self) -> tuple[Budget, ...]:
        rows = self.conn.execute("select * from budgets").fetchall()
        return tuple(
            Budget(
                category_slug=str(r["category_slug"]),
                limit_paise=int(r["limit_paise"]),
                period_start=date.fromisoformat(str(r["period_start"])),
            )
            for r in rows
        )

    # --- Radar state --------------------------------------------------------

    def acknowledge(self, series_key: str) -> None:
        self.conn.execute(
            "insert or replace into acknowledgements (series_key, acknowledged_at)"
            " values (?,?)",
            (series_key, _now()),
        )
        self.conn.commit()

    def unacknowledge(self, series_key: str) -> None:
        self.conn.execute("delete from acknowledgements where series_key = ?", (series_key,))
        self.conn.commit()

    def acknowledged(self) -> set[str]:
        return {
            str(r["series_key"])
            for r in self.conn.execute("select series_key from acknowledgements").fetchall()
        }

    def dismiss(self, anomaly_key: str) -> None:
        self.conn.execute(
            "insert or replace into dismissals (anomaly_key, dismissed_at) values (?,?)",
            (anomaly_key, _now()),
        )
        self.conn.commit()

    def dismissed(self) -> set[str]:
        return {
            str(r["anomaly_key"])
            for r in self.conn.execute("select anomaly_key from dismissals").fetchall()
        }

    # --- Soft delete --------------------------------------------------------

    def soft_delete_transaction(self, txn_id: str, *, reason: str | None = None) -> None:
        """Hide one transaction from every read path, reversibly.

        `insert or replace` keyed on `txn_id` makes this idempotent, so a
        double-clicked Apply is harmless.
        """
        self.conn.execute(
            "insert or replace into deleted_transactions (txn_id, deleted_at, reason) "
            "values (?,?,?)",
            (txn_id, _now(), reason),
        )
        self.conn.commit()

    def restore_transaction(self, txn_id: str) -> None:
        self.conn.execute("delete from deleted_transactions where txn_id = ?", (txn_id,))
        self.conn.commit()

    def deleted_transaction_ids(self) -> set[str]:
        return {
            str(r["txn_id"])
            for r in self.conn.execute("select txn_id from deleted_transactions").fetchall()
        }

    # --- Budget Guard (browser extension) -----------------------------------

    def record_guard_event(
        self, *, site: str, outcome: str, cart_paise: int, discretionary_paise: int
    ) -> str:
        eid = uuid.uuid4().hex
        self.conn.execute(
            "insert into guard_events "
            "(id, created_at, site, outcome, cart_paise, discretionary_paise) "
            "values (?,?,?,?,?,?)",
            (eid, _now(), site, outcome, int(cart_paise), int(discretionary_paise)),
        )
        self.conn.commit()
        return eid

    def guard_events(self, limit: int = 20) -> list[dict[str, Any]]:
        return [
            dict(r)
            for r in self.conn.execute(
                "select * from guard_events order by created_at desc limit ?", (limit,)
            ).fetchall()
        ]

    def transaction_exists(self, txn_id: str) -> bool:
        """Is this a real, not-already-removed transaction id?"""
        row = self.conn.execute(
            "select 1 from transactions "
            "where id = ? and id not in (select txn_id from deleted_transactions)",
            (txn_id,),
        ).fetchone()
        return row is not None

    # --- Privacy ------------------------------------------------------------

    def record_disclosure(
        self, *, purpose: str, model: str, field_types: Iterable[str], redacted_count: int
    ) -> None:
        """Field *names* only. Values must never reach this table (DESIGN.md 12.1)."""
        self.conn.execute(
            "insert into ai_disclosures (id, created_at, purpose, model, field_types,"
            " redacted_count) values (?,?,?,?,?,?)",
            (_new_id(), _now(), purpose, model, json.dumps(sorted(set(field_types))),
             int(redacted_count)),
        )
        self.conn.commit()

    def disclosures(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "select * from ai_disclosures order by created_at desc limit 200"
        ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item["field_types"] = json.loads(str(item["field_types"]))
            out.append(item)
        return out

    def set_consent(self, *, version: str, scope: str, granted: bool) -> None:
        self.conn.execute(
            "insert into consents (id, created_at, version, scope, granted)"
            " values (?,?,?,?,?)",
            (_new_id(), _now(), version, scope, 1 if granted else 0),
        )
        self.conn.commit()

    def consents(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "select * from consents order by created_at desc"
        ).fetchall()
        return [dict(r) for r in rows]

    def consent_granted(self, scope: str) -> bool:
        row = self.conn.execute(
            "select granted from consents where scope = ? order by created_at desc limit 1",
            (scope,),
        ).fetchone()
        return bool(row and row["granted"])

    # --- Vault --------------------------------------------------------------

    def erase_everything(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for table in _USER_TABLES:
            counts[table] = int(
                self.conn.execute("select count(*) c from " + table).fetchone()["c"]
            )
            self.conn.execute("delete from " + table)
        # Erasure disconnects Gmail too, but the count is reported separately
        # from export/inventory since this table also holds a refresh token.
        counts["email_connections"] = int(
            self.conn.execute("select count(*) c from email_connections").fetchone()["c"]
        )
        self.conn.execute("delete from email_connections")
        self.conn.commit()
        return counts

    def export_everything(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "exported_at": _now(),
            "schema_version": "1.0.0",
        }
        for table in _USER_TABLES:
            rows = self.conn.execute("select * from " + table).fetchall()
            payload[table] = [dict(r) for r in rows]
        return payload

    def storage_inventory(self) -> list[dict[str, Any]]:
        out = []
        for table in _USER_TABLES:
            count = int(self.conn.execute("select count(*) c from " + table).fetchone()["c"])
            out.append({"table": table, "row_count": count})
        # Masked count only — never the row itself, which carries a refresh
        # token (DESIGN.md 12.1's field-names-not-values rule, applied here).
        email_count = int(
            self.conn.execute("select count(*) c from email_connections").fetchone()["c"]
        )
        out.append({"table": "email_connections", "row_count": email_count})
        return out

    # --- Gmail connection -----------------------------------------------------

    def set_email_connection(self, *, email_address: str, refresh_token: str) -> None:
        """Replaces any existing connection — one Gmail account for the app."""
        self.conn.execute("delete from email_connections")
        self.conn.execute(
            "insert into email_connections (id, provider, email_address,"
            " refresh_token, created_at) values (?,?,?,?,?)",
            (_new_id(), "gmail", email_address, refresh_token, _now()),
        )
        self.conn.commit()

    def email_connection(self) -> dict[str, Any] | None:
        row = self.conn.execute("select * from email_connections limit 1").fetchone()
        return dict(row) if row else None

    def clear_email_connection(self) -> None:
        self.conn.execute("delete from email_connections")
        self.conn.commit()

    def mark_email_synced(self, *, last_message_internal_date: str) -> None:
        self.conn.execute(
            "update email_connections set last_synced_at = ?,"
            " last_message_internal_date = ?",
            (_now(), last_message_internal_date),
        )
        self.conn.commit()
