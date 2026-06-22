"""Validate CSV headers in a delivery package against data contract v1.

Checks that every CSV file in the delivery package contains at least the
required columns defined by the contract. Optional columns are ignored.
No data leaves the machine — this reads only local files.

Usage:
    python bank_gen/_validate_delivery.py --delivery ./delivery --bank-id bank-a
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from bank_gen.deliver import (
    ACCOUNT_V1_REQUIRED,
    CUSTOMER_V1_FIELDS,
    TRANSACTION_V1_REQUIRED,
)


def _read_header(path: Path) -> set[str]:
    with path.open("r", encoding="utf-8") as f:
        return set(next(csv.reader(f)))


def validate(delivery_dir: Path, bank_id: str) -> list[str]:
    """Return a list of error messages (empty = all OK)."""
    errors: list[str] = []
    base = delivery_dir / bank_id

    if not base.is_dir():
        return [f"Delivery directory not found: {base}"]

    # Validate all CSVs found under base/
    for csv_path in sorted(base.rglob("*.csv")):
        try:
            header = _read_header(csv_path)
        except StopIteration:
            errors.append(f"{csv_path}: empty file (no header row)")
            continue
        except Exception as exc:
            errors.append(f"{csv_path}: could not read — {exc}")
            continue

        name = csv_path.stem  # customers / accounts / transactions
        if name == "customers":
            required = set(CUSTOMER_V1_FIELDS)
        elif name == "accounts":
            required = set(ACCOUNT_V1_REQUIRED)
        elif name == "transactions":
            required = set(TRANSACTION_V1_REQUIRED)
        else:
            # Unknown file — skip silently
            continue

        missing = required - header
        if missing:
            errors.append(
                f"{csv_path.relative_to(delivery_dir)}: "
                f"missing columns {sorted(missing)}"
            )

    return errors


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Validate delivery package CSV headers against contract v1"
    )
    p.add_argument("--delivery", default="./delivery",
                   help="Delivery root directory (default: ./delivery)")
    p.add_argument("--bank-id", default="bank-a",
                   help="tenant id (default: bank-a)")
    args = p.parse_args(argv)

    delivery_dir = Path(args.delivery)
    errors = validate(delivery_dir, args.bank_id)

    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print(f"  ✗ {e}")
        return 1

    # Count validated files
    base = delivery_dir / args.bank_id
    files = list(base.rglob("*.csv"))
    print(f"OK — {len(files)} CSV file(s) validated against contract v1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
