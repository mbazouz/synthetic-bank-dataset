"""Memory-bounded contract v1 delivery for very large transaction sets.

Drop-in alternative to `python -m bank_gen.deliver` for cases where
transactions.csv is too large to hold in RAM (the stock deliver loads the
whole file into a list of dicts twice, which OOMs on tens of millions of rows).

Differences vs bank_gen.deliver:
  * Transactions are STREAMED row-by-row (constant memory, ~tens of MB) instead
    of fully loaded + globally sorted.
  * Transaction integer IDs are therefore assigned in FILE order, not in global
    (timestamp, account_id) order. They remain unique, deterministic for a given
    input file, and fully contract-v1 valid. Only use this when there is no prior
    delivery whose time-ordered IDs must be preserved.
  * Customers/accounts (small) are handled exactly as in bank_gen.deliver — same
    mapping, same stable integer IDs (sorted by source UUID).
  * Delta partitions are NOT supported here (full load only). cutoff should cover
    the whole window.

Usage:
    python stream_deliver.py --output ./output-2k-10y --delivery ./delivery \
        --bank-id bank-seven --cutoff 2026-06-05
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
from datetime import date
from pathlib import Path

# Reuse the canonical schemas + mapping helpers from the stock deliver module so
# the wire format stays byte-identical (minus tx id ordering).
from bank_gen.deliver import (
    ACCOUNT_V1_FIELDS,
    CUSTOMER_V1_FIELDS,
    TRANSACTION_V1_FIELDS,
    _ascii_name,
    _bool_v1,
    _map_account_role,
    _read_csv,
    _tx_date,
    _write_csv,
)
from bank_gen.locales import get_locale

# csv module's default field-size limit (128 KB) is plenty for our labels, but
# bump it defensively so a pathological row never aborts the whole stream.
csv.field_size_limit(10 * 1024 * 1024)


def stream_deliver(
    output_dir: Path, delivery_dir: Path, bank_id: str, cutoff: date
) -> dict[str, int]:
    output_dir = Path(output_dir)
    delivery_dir = Path(delivery_dir)

    # --- small entities fully in memory (2k customers / 6k accounts) ---------
    customers_raw = _read_csv(output_dir / "customers.csv")
    accounts_raw = _read_csv(output_dir / "accounts.csv")
    customers_raw.sort(key=lambda r: r["customer_id"])
    accounts_raw.sort(key=lambda r: r["account_id"])

    cust_id_map = {r["customer_id"]: i + 1 for i, r in enumerate(customers_raw)}
    acc_id_map = {r["account_id"]: i + 1 for i, r in enumerate(accounts_raw)}

    first_iban: dict[str, str] = {}
    current_iban: dict[str, str] = {}
    for acc in accounts_raw:
        cid = acc["customer_id"]
        first_iban.setdefault(cid, acc.get("iban", ""))
        if acc.get("role", "").strip().upper() == "CURRENT" and cid not in current_iban:
            current_iban[cid] = acc.get("iban", "")

    def _customer_iban(cid: str) -> str:
        return current_iban.get(cid) or first_iban.get(cid, "")

    base = delivery_dir / bank_id
    full_dir = base / "full" / cutoff.isoformat()

    # --- customers.csv -------------------------------------------------------
    customers_v1 = []
    for r in customers_raw:
        cid_raw = r["customer_id"]
        seq = cust_id_map[cid_raw]
        revenu = float(r.get("monthly_income", 0) or 0)
        loc = get_locale(r.get("locale_code") or "fr")
        first, last = r.get("first_name", ""), r.get("last_name", "")
        customers_v1.append({
            "id": seq,
            "first_name": first,
            "last_name": last,
            "email": f"{_ascii_name(first)}.{_ascii_name(last)}.{seq}@synthbank.example",
            "phone": loc.phone_format(seq),
            "iban": _customer_iban(cid_raw),
            "address": loc.street_format(seq, random.Random(seq)),
            "postal_code": r.get("postal_code", ""),
            "city": r.get("city", ""),
            "dob": r.get("birth_date", ""),
            "annual_income_eur": round(revenu * 12),
        })
    _write_csv(full_dir / "customers.csv", CUSTOMER_V1_FIELDS, customers_v1)

    # --- accounts.csv --------------------------------------------------------
    accounts_v1 = []
    for r in accounts_raw:
        accounts_v1.append({
            "id": acc_id_map[r["account_id"]],
            "customer_id": cust_id_map.get(r["customer_id"], 0),
            "iban": r.get("iban", ""),
            "opened_at": r.get("opened_at", ""),
            "type": _map_account_role(r.get("role", "")),
            "balance_current": r.get("current_balance", ""),
            "overdraft_limit": r.get("overdraft_limit", "0"),
        })
    _write_csv(full_dir / "accounts.csv", ACCOUNT_V1_FIELDS, accounts_v1)

    # --- transactions.csv: STREAM in, STREAM out -----------------------------
    tx_in = output_dir / "transactions.csv"
    tx_out = full_dir / "transactions.csv"
    tx_out.parent.mkdir(parents=True, exist_ok=True)

    n = 0
    skipped = 0
    with tx_in.open("r", encoding="utf-8", newline="") as fin, \
         tx_out.open("w", encoding="utf-8", newline="") as fout:
        reader = csv.DictReader(fin)
        writer = csv.DictWriter(fout, fieldnames=TRANSACTION_V1_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in reader:
            d = _tx_date(row)
            if d > cutoff:
                skipped += 1
                continue
            n += 1
            writer.writerow({
                "id": n,
                "account_id": acc_id_map.get(row.get("account_id", ""), 0),
                "customer_id": cust_id_map.get(row.get("customer_id", ""), 0),
                "date": d.isoformat(),
                "amount": row.get("amount", ""),
                "label": row.get("label", ""),
                "category": row.get("category", ""),
                "balance_after_transaction": row.get("balance_after_transaction", ""),
                "is_cash_withdrawal": _bool_v1(row.get("is_cash_withdrawal")),
                "is_subscription": _bool_v1(row.get("is_subscription")),
                "is_salary": _bool_v1(row.get("is_salary")),
                "is_transfer": _bool_v1(row.get("is_transfer")),
                "mcc": row.get("merchant_mcc", ""),
            })
            if n % 1_000_000 == 0:
                print(f"  ... {n:,} transactions written", flush=True)

    return {
        "customers": len(customers_v1),
        "accounts": len(accounts_v1),
        "full_transactions": n,
        "skipped_after_cutoff": skipped,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Memory-bounded contract v1 delivery")
    p.add_argument("--output", default="./output")
    p.add_argument("--delivery", default="./delivery")
    p.add_argument("--bank-id", default="bank-a")
    p.add_argument("--cutoff", required=True, help="Full-load cutoff date (YYYY-MM-DD)")
    args = p.parse_args(argv)

    counts = stream_deliver(
        Path(args.output), Path(args.delivery), args.bank_id, date.fromisoformat(args.cutoff)
    )
    print(f"Delivery package → {Path(args.delivery) / args.bank_id}")
    for label, count in counts.items():
        print(f"  {label}: {count:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
