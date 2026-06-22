"""Streaming writers for CSV and Parquet output.

All writers buffer up to N rows in memory then flush. CSV is the canonical
output (PostgreSQL-COPY compatible). Parquet is emitted via pyarrow when
requested — it writes row groups of `batch_size` rows so very large outputs
remain memory bounded.
"""
from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Iterable, Iterator

import pyarrow as pa
import pyarrow.parquet as pq


class StreamingCsvWriter:
    """Append rows to a CSV file, buffered, with a known header."""

    def __init__(self, path: Path, fieldnames: list[str], batch_size: int = 50_000):
        self.path = path
        self.fieldnames = fieldnames
        self.batch_size = batch_size
        self.buffer: list[dict] = []
        self._fh = None
        self._writer = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._fh, fieldnames=self.fieldnames)
        self._writer.writeheader()
        return self

    def write(self, row: dict) -> None:
        self.buffer.append(row)
        if len(self.buffer) >= self.batch_size:
            self.flush()

    def flush(self) -> None:
        if not self.buffer:
            return
        self._writer.writerows(self.buffer)
        self.buffer.clear()

    def __exit__(self, exc_type, exc, tb):
        self.flush()
        if self._fh:
            self._fh.close()


class StreamingParquetWriter:
    """Buffer rows then write Parquet row groups via pyarrow."""

    def __init__(self, path: Path, schema: pa.Schema, batch_size: int = 50_000):
        self.path = path
        self.schema = schema
        self.batch_size = batch_size
        self.buffer: list[dict] = []
        self._writer: pq.ParquetWriter | None = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._writer = pq.ParquetWriter(self.path, self.schema, compression="snappy")
        return self

    def write(self, row: dict) -> None:
        self.buffer.append(row)
        if len(self.buffer) >= self.batch_size:
            self.flush()

    def flush(self) -> None:
        if not self.buffer:
            return
        columns = {name: [] for name in self.schema.names}
        for row in self.buffer:
            for name in self.schema.names:
                columns[name].append(row.get(name))
        table = pa.Table.from_pydict(columns, schema=self.schema)
        self._writer.write_table(table)
        self.buffer.clear()

    def __exit__(self, exc_type, exc, tb):
        self.flush()
        if self._writer:
            self._writer.close()


# Schemas for parquet output (transactions only — biggest table)
TRANSACTION_PARQUET_SCHEMA = pa.schema([
    ("transaction_id", pa.string()),
    ("account_id", pa.string()),
    ("customer_id", pa.string()),
    ("timestamp", pa.string()),
    ("amount", pa.float64()),
    ("currency", pa.string()),
    ("merchant_name", pa.string()),
    ("merchant_category", pa.string()),
    ("merchant_mcc", pa.string()),
    ("transaction_type", pa.string()),
    ("payment_channel", pa.string()),
    ("city", pa.string()),
    ("country", pa.string()),
    ("counterparty_iban", pa.string()),
    ("label", pa.string()),
    ("category", pa.string()),
    ("subcategory", pa.string()),
    ("is_subscription", pa.bool_()),
    ("is_salary", pa.bool_()),
    ("is_transfer", pa.bool_()),
    ("is_cash_withdrawal", pa.bool_()),
    ("balance_after_transaction", pa.float64()),
])


TRANSACTION_FIELDS = [f.name for f in TRANSACTION_PARQUET_SCHEMA]


def write_rows_csv(path: Path, fieldnames: list[str], rows: Iterable[dict]) -> int:
    """Write a small table in one shot."""
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            n += 1
    return n
