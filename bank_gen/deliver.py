"""Delivery exporter: bank_gen raw output → data contract v1 package.

Simulates a real bank delivering its data by converting the rich
French-format bank_gen output into the data contract v1 wire format
(see "Data contract v1" in README.md) and structuring it in an S3-mirror
directory hierarchy.

Layout produced:

    <delivery_dir>/<bank_id>/full/<cutoff_date>/
        customers.csv       — all customers (required + optional v1 columns)
        accounts.csv        — all accounts (required + optional v1 columns)
        transactions.csv    — transactions with date ≤ cutoff_date

    <delivery_dir>/<bank_id>/delta/<delta_date>/
        transactions.csv    — transactions where prev_cutoff < date ≤ delta_date

External IDs are stable integers assigned by sorted order of bank_gen UUIDs.
Given the same seed, successive runs always produce the same integer IDs —
a customer always keeps their ID across full and delta deliveries.

Usage (CLI):
    python -m bank_gen.deliver \\
        --output ./output \\
        --delivery ./delivery \\
        --bank-id bank-a \\
        --cutoff 2024-03-31 \\
        --deltas 2024-04-30 2024-05-31

Usage (library):
    from bank_gen.deliver import build_delivery_package
    counts = build_delivery_package(output_dir, delivery_dir, bank_id, cutoff, delta_dates)
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path

from .locales import get_locale


# ---------------------------------------------------------------------------
# data contract v1 column schemas
# ---------------------------------------------------------------------------

CUSTOMER_V1_FIELDS = [
    "id", "first_name", "last_name", "email", "phone", "iban",
    "address", "postal_code", "city", "dob", "annual_income_eur",
]

ACCOUNT_V1_REQUIRED = ["id", "customer_id", "iban", "opened_at", "type"]
ACCOUNT_V1_OPTIONAL = ["balance_current", "overdraft_limit"]
ACCOUNT_V1_FIELDS = ACCOUNT_V1_REQUIRED + ACCOUNT_V1_OPTIONAL

TRANSACTION_V1_REQUIRED = [
    "id", "account_id", "customer_id", "date", "amount", "label", "category",
]
TRANSACTION_V1_OPTIONAL = [
    "balance_after_transaction", "is_cash_withdrawal",
    "is_subscription", "is_salary", "is_transfer", "mcc",
]
TRANSACTION_V1_FIELDS = TRANSACTION_V1_REQUIRED + TRANSACTION_V1_OPTIONAL


# ---------------------------------------------------------------------------
# Account role → canonical contract type
# ---------------------------------------------------------------------------

_ROLE_TO_CONTRACT: dict[str, str] = {
    "CURRENT":      "CURRENT",
    "JOINT":        "CURRENT",
    "BUSINESS":     "CURRENT",
    "SAVINGS":      "SAVINGS",
    "HOME_SAVINGS": "SAVINGS",
    "INVEST":       "SAVINGS",
    "RETIREMENT":   "SAVINGS",
}


def _map_account_role(role: str) -> str:
    return _ROLE_TO_CONTRACT.get((role or "").strip().upper(), "CURRENT")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ascii_name(s: str) -> str:
    """Remove diacritics and keep only ASCII letters (for email generation)."""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(
        c for c in nfkd if not unicodedata.combining(c) and c.isalpha()
    ).lower()


def _bool_v1(value: str | bool | None) -> str:
    """Normalise any bool-like value to the contract token 'true'/'false'."""
    if value is None or value == "":
        return "false"
    if isinstance(value, bool):
        return "true" if value else "false"
    return "true" if str(value).strip().lower() in {"true", "1", "t", "yes"} else "false"


def _tx_date(row: dict) -> date:
    """Extract the date part from a bank_gen transaction row's 'timestamp' field."""
    ts = row.get("timestamp", "")
    return datetime.fromisoformat(ts).date()


def _read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, fields: list[str], rows: list[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------

def build_delivery_package(
    output_dir: Path,
    delivery_dir: Path,
    bank_id: str,
    cutoff_date: date,
    delta_dates: list[date],
) -> dict[str, int]:
    """Build a data contract v1 delivery package from bank_gen output.

    Args:
        output_dir:   Directory containing bank_gen's customers.csv, accounts.csv,
                      transactions.csv.
        delivery_dir: Root directory where the delivery package is written.
        bank_id:      tenant identifier (e.g. 'bank-a').
        cutoff_date:  Last date included in the full load.
        delta_dates:  Sorted list of dates; each produces one delta/
                      subdirectory covering (prev_cutoff, delta_date].

    Returns:
        A dict with row counts keyed by load label, e.g.
        {"customers": 500, "accounts": 1200, "full_transactions": 42000,
         "delta_2024-04-30": 3500, ...}
    """
    # 1. Load raw bank_gen CSVs -------------------------------------------
    customers_raw = _read_csv(output_dir / "customers.csv")
    accounts_raw = _read_csv(output_dir / "accounts.csv")
    transactions_raw = _read_csv(output_dir / "transactions.csv")

    # 2. Build stable integer ID maps (sorted by UUID → deterministic) ----
    customers_raw.sort(key=lambda r: r["customer_id"])
    accounts_raw.sort(key=lambda r: r["account_id"])

    cust_id_map: dict[str, int] = {
        r["customer_id"]: i + 1 for i, r in enumerate(customers_raw)
    }
    acc_id_map: dict[str, int] = {
        r["account_id"]: i + 1 for i, r in enumerate(accounts_raw)
    }

    # 3. Derive customer IBAN (prefer first compte_courant, else first account)
    # Accounts are already sorted — we build a two-pass map.
    first_iban: dict[str, str] = {}
    current_iban: dict[str, str] = {}
    for acc in accounts_raw:
        cid = acc["customer_id"]
        if cid not in first_iban:
            first_iban[cid] = acc.get("iban", "")
        if (acc.get("role", "").strip().upper() == "CURRENT") and cid not in current_iban:
            current_iban[cid] = acc.get("iban", "")

    def _customer_iban(cid: str) -> str:
        return current_iban.get(cid) or first_iban.get(cid, "")

    # 4. Map customers → contract v1 --------------------------------------
    customers_v1: list[dict] = []
    for r in customers_raw:
        cid_raw = r["customer_id"]
        seq = cust_id_map[cid_raw]
        prenom_a = _ascii_name(r.get("first_name", ""))
        nom_a = _ascii_name(r.get("last_name", ""))
        revenu = float(r.get("monthly_income", 0) or 0)
        loc = get_locale(r.get("locale_code") or "fr")
        pii_rng = random.Random(seq)
        customers_v1.append({
            "id": seq,
            "first_name": r.get("first_name", ""),
            "last_name": r.get("last_name", ""),
            # email: deterministic — never a real address (no PII risk)
            "email": f"{prenom_a}.{nom_a}.{seq}@synthbank.example",
            # phone: synthetic, locale-shaped (never a real number)
            "phone": loc.phone_format(seq),
            "iban": _customer_iban(cid_raw),
            # address: synthetic, locale-shaped (bank_gen exports no street address)
            "address": loc.street_format(seq, pii_rng),
            "postal_code": r.get("postal_code", ""),
            "city": r.get("city", ""),
            "dob": r.get("birth_date", ""),
            "annual_income_eur": round(revenu * 12),
        })

    # 5. Map accounts → contract v1 ----------------------------------------
    accounts_v1: list[dict] = []
    for r in accounts_raw:
        acc_id = acc_id_map[r["account_id"]]
        cust_id = cust_id_map.get(r["customer_id"], 0)
        accounts_v1.append({
            "id": acc_id,
            "customer_id": cust_id,
            "iban": r.get("iban", ""),
            "opened_at": r.get("opened_at", ""),
            "type": _map_account_role(r.get("role", "")),
            "balance_current": r.get("current_balance", ""),
            "overdraft_limit": r.get("overdraft_limit", "0"),
        })

    # 6. Sort transactions for stable sequential IDs ----------------------
    # Sort by (timestamp, account_id) so the same seed always yields the
    # same integer IDs even when transaction_ids are random UUIDs.
    transactions_raw.sort(
        key=lambda r: (r.get("timestamp", ""), r.get("account_id", ""))
    )

    def _map_tx(row: dict, tx_id: int) -> dict:
        return {
            "id": tx_id,
            "account_id": acc_id_map.get(row.get("account_id", ""), 0),
            "customer_id": cust_id_map.get(row.get("customer_id", ""), 0),
            "date": _tx_date(row).isoformat(),
            "amount": row.get("amount", ""),
            "label": row.get("label", ""),
            "category": row.get("category", ""),
            "balance_after_transaction": row.get("balance_after_transaction", ""),
            "is_cash_withdrawal": _bool_v1(row.get("is_cash_withdrawal")),
            "is_subscription": _bool_v1(row.get("is_subscription")),
            "is_salary": _bool_v1(row.get("is_salary")),
            "is_transfer": _bool_v1(row.get("is_transfer")),
            "mcc": row.get("merchant_mcc", ""),
        }

    # 7. Partition transactions by date -----------------------------------
    full_txns = [r for r in transactions_raw if _tx_date(r) <= cutoff_date]
    pending = [r for r in transactions_raw if _tx_date(r) > cutoff_date]

    # 8. Write full load -------------------------------------------------
    base = delivery_dir / bank_id
    full_dir = base / "full" / cutoff_date.isoformat()

    _write_csv(full_dir / "customers.csv", CUSTOMER_V1_FIELDS, customers_v1)
    _write_csv(full_dir / "accounts.csv", ACCOUNT_V1_FIELDS, accounts_v1)

    full_tx_v1 = [_map_tx(r, i + 1) for i, r in enumerate(full_txns)]
    _write_csv(full_dir / "transactions.csv", TRANSACTION_V1_FIELDS, full_tx_v1)

    # 9. Write deltas ----------------------------------------------------
    next_tx_id = len(full_txns) + 1
    prev_cutoff = cutoff_date
    delta_counts: dict[str, int] = {}

    for delta_date in sorted(delta_dates):
        delta_txns = [
            r for r in pending
            if prev_cutoff < _tx_date(r) <= delta_date
        ]
        # remove from pending (consumed)
        pending = [r for r in pending if _tx_date(r) > delta_date or _tx_date(r) <= prev_cutoff]

        delta_dir = base / "delta" / delta_date.isoformat()
        delta_tx_v1 = []
        for row in delta_txns:
            delta_tx_v1.append(_map_tx(row, next_tx_id))
            next_tx_id += 1
        _write_csv(delta_dir / "transactions.csv", TRANSACTION_V1_FIELDS, delta_tx_v1)
        delta_counts[f"delta_{delta_date.isoformat()}"] = len(delta_tx_v1)
        prev_cutoff = delta_date

    return {
        "customers": len(customers_v1),
        "accounts": len(accounts_v1),
        "full_transactions": len(full_txns),
        **delta_counts,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Deliver a data contract v1 package from bank_gen output"
    )
    p.add_argument("--output", default="./output",
                   help="bank_gen output directory (source, default: ./output)")
    p.add_argument("--delivery", default="./delivery",
                   help="delivery root directory (destination, default: ./delivery)")
    p.add_argument("--bank-id", default="bank-a",
                   help="tenant id (default: bank-a)")
    p.add_argument("--cutoff", required=True,
                   help="Full-load cutoff date (YYYY-MM-DD). Transactions on or before this date go into full/.")
    p.add_argument("--deltas", nargs="*", default=[],
                   help="Delta cutoff dates (YYYY-MM-DD ...). Each produces a delta/ subdirectory.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    output_dir = Path(args.output)
    delivery_dir = Path(args.delivery)
    cutoff = date.fromisoformat(args.cutoff)
    deltas = [date.fromisoformat(d) for d in (args.deltas or [])]

    customers_path = output_dir / "customers.csv"
    if not customers_path.exists():
        print(
            f"ERROR: {customers_path} not found. Run `make generate` first.",
            file=sys.stderr,
        )
        return 1

    counts = build_delivery_package(output_dir, delivery_dir, args.bank_id, cutoff, deltas)
    print(f"Delivery package → {delivery_dir / args.bank_id}")
    for label, count in counts.items():
        print(f"  {label}: {count:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
