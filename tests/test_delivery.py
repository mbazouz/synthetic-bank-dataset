"""E2E test harness for bank_gen.deliver.

Tests exercise the full pipeline: generate → deliver → verify contract v1.
A small dataset (50 customers, 6 months) keeps each test under 30 s.

No external services required — all I/O is to tmp_path.
"""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest

from bank_gen.deliver import (
    ACCOUNT_V1_FIELDS,
    CUSTOMER_V1_FIELDS,
    TRANSACTION_V1_FIELDS,
    build_delivery_package,
)
from bank_gen.deliver import ACCOUNT_V1_REQUIRED, TRANSACTION_V1_REQUIRED
from bank_gen.main import main as generate_main

# ---------------------------------------------------------------------------
# Fixture: small dataset generated once per session
# ---------------------------------------------------------------------------

CUSTOMERS = 50
START = "2023-01-01"
END = "2023-12-31"
SEED = 9999
CUTOFF = date(2023, 6, 30)
DELTA1 = date(2023, 9, 30)
DELTA2 = date(2023, 12, 31)


@pytest.fixture(scope="session")
def output_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate a small bank dataset into a session-scoped temp dir."""
    out = tmp_path_factory.mktemp("output")
    rc = generate_main([
        "--customers", str(CUSTOMERS),
        "--start", START,
        "--end", END,
        "--output", str(out),
        "--seed", str(SEED),
    ])
    assert rc == 0, "bank_gen.main failed"
    return out


@pytest.fixture(scope="session")
def delivery_dir(tmp_path_factory: pytest.TempPathFactory, output_dir: Path) -> Path:
    """Run the delivery exporter and return the delivery root."""
    delivery = tmp_path_factory.mktemp("delivery")
    counts = build_delivery_package(
        output_dir=output_dir,
        delivery_dir=delivery,
        bank_id="bank-a",
        cutoff_date=CUTOFF,
        delta_dates=[DELTA1, DELTA2],
    )
    assert counts["customers"] == CUSTOMERS
    assert counts["accounts"] >= CUSTOMERS  # ≥1 account per customer
    assert counts["full_transactions"] > 0
    return delivery


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_header(path: Path) -> set[str]:
    with path.open("r", encoding="utf-8") as f:
        return set(next(csv.reader(f)))


def _read_all(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _full_dir(delivery_dir: Path) -> Path:
    return delivery_dir / "bank-a" / "full" / CUTOFF.isoformat()


def _delta_dir(delivery_dir: Path, d: date) -> Path:
    return delivery_dir / "bank-a" / "delta" / d.isoformat()


# ---------------------------------------------------------------------------
# Tests: directory structure
# ---------------------------------------------------------------------------

def test_full_load_directory_exists(delivery_dir: Path) -> None:
    assert _full_dir(delivery_dir).is_dir()


def test_delta_directories_exist(delivery_dir: Path) -> None:
    assert _delta_dir(delivery_dir, DELTA1).is_dir()
    assert _delta_dir(delivery_dir, DELTA2).is_dir()


def test_full_load_contains_all_three_files(delivery_dir: Path) -> None:
    full = _full_dir(delivery_dir)
    assert (full / "customers.csv").is_file()
    assert (full / "accounts.csv").is_file()
    assert (full / "transactions.csv").is_file()


def test_delta_contains_only_transactions(delivery_dir: Path) -> None:
    """Deltas carry only transactions — customers/accounts are in the full load."""
    delta1 = _delta_dir(delivery_dir, DELTA1)
    assert (delta1 / "transactions.csv").is_file()
    assert not (delta1 / "customers.csv").exists()
    assert not (delta1 / "accounts.csv").exists()


# ---------------------------------------------------------------------------
# Tests: contract v1 headers
# ---------------------------------------------------------------------------

def test_customers_has_required_columns(delivery_dir: Path) -> None:
    header = _read_header(_full_dir(delivery_dir) / "customers.csv")
    assert set(CUSTOMER_V1_FIELDS) <= header, \
        f"Missing: {set(CUSTOMER_V1_FIELDS) - header}"


def test_accounts_has_required_columns(delivery_dir: Path) -> None:
    header = _read_header(_full_dir(delivery_dir) / "accounts.csv")
    assert set(ACCOUNT_V1_REQUIRED) <= header, \
        f"Missing: {set(ACCOUNT_V1_REQUIRED) - header}"


def test_full_transactions_has_required_columns(delivery_dir: Path) -> None:
    header = _read_header(_full_dir(delivery_dir) / "transactions.csv")
    assert set(TRANSACTION_V1_REQUIRED) <= header, \
        f"Missing: {set(TRANSACTION_V1_REQUIRED) - header}"


def test_delta_transactions_has_required_columns(delivery_dir: Path) -> None:
    header = _read_header(_delta_dir(delivery_dir, DELTA1) / "transactions.csv")
    assert set(TRANSACTION_V1_REQUIRED) <= header, \
        f"Missing: {set(TRANSACTION_V1_REQUIRED) - header}"


# ---------------------------------------------------------------------------
# Tests: stable external IDs
# ---------------------------------------------------------------------------

def test_customer_ids_are_positive_integers(delivery_dir: Path) -> None:
    rows = _read_all(_full_dir(delivery_dir) / "customers.csv")
    ids = [int(r["id"]) for r in rows]
    assert all(i > 0 for i in ids)
    assert len(ids) == len(set(ids)), "Customer IDs must be unique"


def test_account_ids_are_positive_integers(delivery_dir: Path) -> None:
    rows = _read_all(_full_dir(delivery_dir) / "accounts.csv")
    ids = [int(r["id"]) for r in rows]
    assert all(i > 0 for i in ids)
    assert len(ids) == len(set(ids)), "Account IDs must be unique"


def test_full_transaction_ids_are_sequential_integers(delivery_dir: Path) -> None:
    rows = _read_all(_full_dir(delivery_dir) / "transactions.csv")
    ids = [int(r["id"]) for r in rows]
    assert ids == list(range(1, len(ids) + 1)), \
        "Full-load transactions must have sequential IDs starting at 1"


def test_delta_ids_continue_from_full(delivery_dir: Path) -> None:
    """Delta transaction IDs must continue from where the full load ended."""
    full_rows = _read_all(_full_dir(delivery_dir) / "transactions.csv")
    delta1_rows = _read_all(_delta_dir(delivery_dir, DELTA1) / "transactions.csv")
    if not delta1_rows:
        pytest.skip("delta1 has no transactions (short date window)")
    full_last_id = int(full_rows[-1]["id"])
    delta1_first_id = int(delta1_rows[0]["id"])
    assert delta1_first_id == full_last_id + 1, \
        f"Expected delta1 to start at {full_last_id + 1}, got {delta1_first_id}"


def test_delta2_ids_continue_from_delta1(delivery_dir: Path) -> None:
    delta1_rows = _read_all(_delta_dir(delivery_dir, DELTA1) / "transactions.csv")
    delta2_rows = _read_all(_delta_dir(delivery_dir, DELTA2) / "transactions.csv")
    if not delta1_rows or not delta2_rows:
        pytest.skip("insufficient rows in deltas")
    delta1_last_id = int(delta1_rows[-1]["id"])
    delta2_first_id = int(delta2_rows[0]["id"])
    assert delta2_first_id == delta1_last_id + 1


# ---------------------------------------------------------------------------
# Tests: date partitioning
# ---------------------------------------------------------------------------

def test_full_transactions_on_or_before_cutoff(delivery_dir: Path) -> None:
    rows = _read_all(_full_dir(delivery_dir) / "transactions.csv")
    for r in rows:
        d = date.fromisoformat(r["date"])
        assert d <= CUTOFF, f"Full load contains txn dated {d} > cutoff {CUTOFF}"


def test_delta1_transactions_in_expected_window(delivery_dir: Path) -> None:
    rows = _read_all(_delta_dir(delivery_dir, DELTA1) / "transactions.csv")
    for r in rows:
        d = date.fromisoformat(r["date"])
        assert CUTOFF < d <= DELTA1, \
            f"Delta1 txn dated {d} outside ({CUTOFF}, {DELTA1}]"


def test_delta2_transactions_in_expected_window(delivery_dir: Path) -> None:
    rows = _read_all(_delta_dir(delivery_dir, DELTA2) / "transactions.csv")
    for r in rows:
        d = date.fromisoformat(r["date"])
        assert DELTA1 < d <= DELTA2, \
            f"Delta2 txn dated {d} outside ({DELTA1}, {DELTA2}]"


def test_no_transaction_id_overlap_across_loads(delivery_dir: Path) -> None:
    """No transaction ID appears in more than one load (full + deltas)."""
    full_ids = {int(r["id"]) for r in _read_all(_full_dir(delivery_dir) / "transactions.csv")}
    d1_ids = {int(r["id"]) for r in _read_all(_delta_dir(delivery_dir, DELTA1) / "transactions.csv")}
    d2_ids = {int(r["id"]) for r in _read_all(_delta_dir(delivery_dir, DELTA2) / "transactions.csv")}
    all_ids = full_ids | d1_ids | d2_ids
    assert len(all_ids) == len(full_ids) + len(d1_ids) + len(d2_ids), \
        "Transaction IDs overlap between full and/or delta loads"


# ---------------------------------------------------------------------------
# Tests: data integrity
# ---------------------------------------------------------------------------

def test_account_customer_ids_reference_valid_customers(delivery_dir: Path) -> None:
    customers = {int(r["id"]) for r in _read_all(_full_dir(delivery_dir) / "customers.csv")}
    accounts = _read_all(_full_dir(delivery_dir) / "accounts.csv")
    for acc in accounts:
        cid = int(acc["customer_id"])
        assert cid in customers, f"Account references unknown customer_id={cid}"


def test_transactions_reference_valid_accounts(delivery_dir: Path) -> None:
    accounts = {int(r["id"]) for r in _read_all(_full_dir(delivery_dir) / "accounts.csv")}
    txns = _read_all(_full_dir(delivery_dir) / "transactions.csv")
    for txn in txns[:500]:  # sample first 500 for speed
        aid = int(txn["account_id"])
        assert aid in accounts, f"Transaction references unknown account_id={aid}"


def test_customers_have_non_empty_email(delivery_dir: Path) -> None:
    rows = _read_all(_full_dir(delivery_dir) / "customers.csv")
    for r in rows:
        assert "@" in r["email"], f"Invalid email: {r['email']}"


def test_customers_have_positive_annual_income(delivery_dir: Path) -> None:
    rows = _read_all(_full_dir(delivery_dir) / "customers.csv")
    for r in rows:
        assert int(r["annual_income_eur"]) > 0


def test_full_and_all_deltas_cover_all_transactions(
    output_dir: Path, delivery_dir: Path
) -> None:
    """Full + delta transaction counts must equal total transactions in window."""
    full_count = sum(1 for _ in _read_all(_full_dir(delivery_dir) / "transactions.csv"))
    d1_count = sum(1 for _ in _read_all(_delta_dir(delivery_dir, DELTA1) / "transactions.csv"))
    d2_count = sum(1 for _ in _read_all(_delta_dir(delivery_dir, DELTA2) / "transactions.csv"))
    delivered_total = full_count + d1_count + d2_count

    # Count raw transactions in the full window (start → DELTA2)
    txns_path = output_dir / "transactions.csv"
    raw_total = 0
    with txns_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            from datetime import datetime
            d = datetime.fromisoformat(row["timestamp"]).date()
            if d <= DELTA2:
                raw_total += 1

    assert delivered_total == raw_total, (
        f"Delivered {delivered_total} transactions but raw data has {raw_total} "
        f"in window [start, {DELTA2}]"
    )
