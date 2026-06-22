"""Orchestrator + CLI.

Usage:
    python -m bank_gen.main \
        --customers 60000 \
        --start 2022-01-01 --end 2024-12-31 \
        --output ./output \
        --seed 4242 \
        --format csv,parquet
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import statistics
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

import numpy as np
from tqdm import tqdm

from .accounts import generate_accounts
from .cards import generate_cards
from .config import (
    BANK_PRESETS,
    DEFAULT_END_DATE,
    DEFAULT_NUM_CUSTOMERS,
    DEFAULT_SEED,
    DEFAULT_START_DATE,
    DEFAULT_TARGET_TRANSACTIONS,
    WRITE_BATCH_SIZE,
)
from .customers import Customer, generate_customers
from .io_writers import (
    TRANSACTION_FIELDS,
    TRANSACTION_PARQUET_SCHEMA,
    StreamingCsvWriter,
    StreamingParquetWriter,
    write_rows_csv,
)
from .loans import generate_loans
from .locales import get_locale
from .merchants import iter_merchants
from .subscriptions import generate_subscriptions
from .trajectory import generate_trajectory
from .transactions import effective_window_start, generate_transactions_for_customer

log = logging.getLogger("bank_gen")


CUSTOMER_FIELDS = [
    "customer_id", "first_name", "last_name", "sex", "age", "birth_date",
    "city", "postal_code", "country", "locale_code", "family_situation", "num_children",
    "profession", "customer_segment", "profile", "bank_preset", "monthly_income",
    "estimated_wealth", "financial_score", "risk_appetite",
    "customer_since",
]

ACCOUNT_FIELDS = [
    "account_id", "customer_id", "iban", "bic", "bank_name", "account_type", "role",
    "opened_at", "initial_balance", "current_balance", "overdraft_limit",
    "status",
]

CARD_FIELDS = [
    "card_id", "account_id", "customer_id", "card_number_masked", "scheme",
    "type", "product", "issued_at", "expires_at", "status",
    "monthly_payment_limit", "monthly_withdrawal_limit", "contactless",
]

SUBSCRIPTION_FIELDS = [
    "subscription_id", "customer_id", "account_id", "merchant_name", "category",
    "subcategory", "amount", "frequency_months", "billing_day", "start_date",
    "end_date", "status",
]

LOAN_FIELDS = [
    "loan_id", "customer_id", "account_id", "loan_type", "principal",
    "outstanding_balance", "annual_rate", "term_months", "monthly_payment", "start_date",
    "end_date", "payment_day", "status",
]

MERCHANT_FIELDS = [
    "merchant_id", "name", "mcc", "category", "subcategory", "amount_mu",
    "amount_sigma", "channel", "weight",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Synthetic banking dataset generator")
    p.add_argument("--country", type=str, default="us", choices=["fr", "us", "uk", "mix"],
                   help="Locale for names, banks, account types, merchants, currency and "
                        "statement wording. 'mix' assigns a country per customer. Default: us.")
    p.add_argument("--customers", type=int, default=DEFAULT_NUM_CUSTOMERS)
    p.add_argument("--start", type=str, default=DEFAULT_START_DATE.isoformat())
    p.add_argument("--end", type=str, default=DEFAULT_END_DATE.isoformat())
    p.add_argument("--output", type=str, default="./output")
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--format", type=str, default="csv",
                   help="Comma-separated list of formats: csv,parquet")
    p.add_argument("--target-transactions", type=int, default=DEFAULT_TARGET_TRANSACTIONS,
                   help="Soft target — used only to scale defaults & report")
    p.add_argument("--bank-presets", type=str, default="all",
                   help="Comma-separated bank preset ids (or 'all'). Each customer is "
                        f"assigned one preset, giving banks distinct mixes. Available: "
                        f"{','.join(BANK_PRESETS)}")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args(argv)


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _resolve_presets(arg: str) -> list[str]:
    arg = (arg or "all").strip().lower()
    if arg == "all":
        return list(BANK_PRESETS.keys())
    ids = [x.strip() for x in arg.split(",") if x.strip()]
    bad = [x for x in ids if x not in BANK_PRESETS]
    if bad:
        raise SystemExit(f"Unknown bank preset(s): {bad}. Available: {list(BANK_PRESETS)}")
    return ids


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    start = _parse_date(args.start)
    end = _parse_date(args.end)
    formats = {f.strip().lower() for f in args.format.split(",") if f.strip()}

    preset_ids = _resolve_presets(args.bank_presets)
    presets = {pid: BANK_PRESETS[pid] for pid in preset_ids}
    preset_weights = {pid: 1.0 for pid in preset_ids}

    log.info("=== synthetic banking dataset ===")
    log.info("Customers: %d | country: %s | window: %s -> %s | seed: %d",
             args.customers, args.country, start, end, args.seed)
    log.info("Bank presets: %s", ", ".join(preset_ids))
    t_global = time.time()

    # ------------------ 1. Customers ----------------------------------------
    t0 = time.time()
    customers = generate_customers(args.customers, seed=args.seed,
                                   presets=presets, preset_weights=preset_weights,
                                   country=args.country)
    log.info("Generated %d customers in %.1fs", len(customers), time.time() - t0)
    # NB: customers.csv is written AFTER trajectories, which update family fields.

    # ------------------ 2. Accounts ----------------------------------------
    t0 = time.time()
    accounts = generate_accounts(customers, seed=args.seed + 100)
    log.info("Generated %d accounts in %.1fs", len(accounts), time.time() - t0)

    customers_by_id: dict[str, Customer] = {c.customer_id: c for c in customers}
    accounts_by_customer: dict[str, list] = {}
    for a in accounts:
        accounts_by_customer.setdefault(a.customer_id, []).append(a)

    # ------------------ 2b. Life trajectories -------------------------------
    # One pass per customer, keyed by the same per-customer seed as the tx loop.
    # The trajectory is the single source of truth consumed by subscriptions,
    # loans and the transaction engine; it also updates family fields so the
    # customer row matches the births/divorces that appear in the stream.
    t0 = time.time()
    trajectories_by_customer: dict[str, object] = {}
    for i, customer in enumerate(customers):
        accs = accounts_by_customer.get(customer.customer_id, [])
        if not accs:
            continue
        eff_start = effective_window_start(customer, accs, start)
        per_seed = (args.seed * 1_000_003 + i) & 0xFFFFFFFF
        preset = BANK_PRESETS.get(customer.bank_preset) or presets[preset_ids[0]]
        traj = generate_trajectory(
            customer, eff_start, end, preset,
            random.Random(per_seed), np.random.default_rng(per_seed),
        )
        trajectories_by_customer[customer.customer_id] = traj
        customer.nombre_enfants = traj.final_children
        customer.situation_familiale = traj.final_situation
    log.info("Generated %d trajectories in %.1fs", len(trajectories_by_customer), time.time() - t0)

    # Now persist customers with trajectory-updated family fields + bank_preset.
    write_rows_csv(output_dir / "customers.csv", CUSTOMER_FIELDS, (c.to_row() for c in customers))

    # ------------------ 3. Cards -------------------------------------------
    t0 = time.time()
    cards = generate_cards(customers_by_id, accounts, seed=args.seed + 200)
    log.info("Generated %d cards in %.1fs", len(cards), time.time() - t0)
    write_rows_csv(output_dir / "cards.csv", CARD_FIELDS, (k.to_row() for k in cards))

    # ------------------ 4. Subscriptions -----------------------------------
    t0 = time.time()
    subs = generate_subscriptions(customers, accounts_by_customer, seed=args.seed + 300,
                                  start_date=start, end_date=end,
                                  trajectories=trajectories_by_customer)
    log.info("Generated %d subscriptions in %.1fs", len(subs), time.time() - t0)
    write_rows_csv(output_dir / "subscriptions.csv", SUBSCRIPTION_FIELDS, (s.to_row() for s in subs))
    subs_by_customer: dict[str, list] = {}
    for s in subs:
        subs_by_customer.setdefault(s.customer_id, []).append(s)

    # ------------------ 5. Loans -------------------------------------------
    t0 = time.time()
    loans = generate_loans(customers, accounts_by_customer, seed=args.seed + 400,
                           horizon_start=start, horizon_end=end,
                           trajectories=trajectories_by_customer)
    log.info("Generated %d loans in %.1fs", len(loans), time.time() - t0)
    write_rows_csv(output_dir / "loans.csv", LOAN_FIELDS, (l.to_row() for l in loans))
    loans_by_customer: dict[str, list] = {}
    for l in loans:
        loans_by_customer.setdefault(l.customer_id, []).append(l)

    # ------------------ 6. Merchants catalogue -----------------------------
    # Single country -> that locale's catalogue; mix -> de-duplicated union.
    if args.country == "mix":
        from .locales import all_locale_codes
        seen: set[str] = set()
        merchant_catalog: list = []
        for code in all_locale_codes():
            for row in get_locale(code).merchants:
                if row[0] not in seen:
                    seen.add(row[0])
                    merchant_catalog.append(row)
    else:
        merchant_catalog = list(get_locale(args.country).merchants)
    write_rows_csv(output_dir / "merchants.csv", MERCHANT_FIELDS, iter_merchants(merchant_catalog))

    # ------------------ 7. Transactions (streaming) ------------------------
    log.info("Generating transactions over %d days for %d customers...",
             (end - start).days + 1, len(customers))
    tx_csv_path = output_dir / "transactions.csv"
    tx_parquet_path = output_dir / "transactions.parquet" if "parquet" in formats else None
    use_csv = "csv" in formats or not formats

    # Customers whose trajectory ends in a terminal (deceased/dormant) phase —
    # used to prove the "standing orders drain until rejection" mechanic fires.
    terminal_ids = {
        cid for cid, t in trajectories_by_customer.items()
        if any(p.status in ("deceased", "dormant") for p in t.phases)
    }

    tx_count = 0
    terminal_rejection_fees = 0
    cm_csv = StreamingCsvWriter(tx_csv_path, TRANSACTION_FIELDS, batch_size=WRITE_BATCH_SIZE)
    cm_pq = (StreamingParquetWriter(tx_parquet_path, TRANSACTION_PARQUET_SCHEMA, batch_size=WRITE_BATCH_SIZE)
             if tx_parquet_path else None)

    t0 = time.time()
    progress = tqdm(total=len(customers), desc="Customers", unit="cust")
    with cm_csv as csv_w:
        if cm_pq is not None:
            cm_pq.__enter__()
        try:
            for i, customer in enumerate(customers):
                accs = accounts_by_customer.get(customer.customer_id, [])
                if not accs:
                    progress.update(1)
                    continue
                per_seed = (args.seed * 1_000_003 + i) & 0xFFFFFFFF
                is_terminal = customer.customer_id in terminal_ids
                loc = get_locale(customer.locale_code)
                for tx in generate_transactions_for_customer(
                    customer, accs,
                    subs_by_customer.get(customer.customer_id, []),
                    loans_by_customer.get(customer.customer_id, []),
                    start, end, per_seed,
                    trajectories_by_customer.get(customer.customer_id),
                ):
                    # Count terminal rejection fees on the RAW token, then
                    # localize taxonomy values for output.
                    if is_terminal and tx["subcategory"] == "agios":
                        terminal_rejection_fees += 1
                    tx["category"] = loc.tx_category(tx["category"])
                    tx["merchant_category"] = loc.tx_category(tx["merchant_category"])
                    tx["subcategory"] = loc.tx_subcategory(tx["subcategory"])
                    if use_csv:
                        csv_w.write(tx)
                    if cm_pq is not None:
                        cm_pq.write(tx)
                    tx_count += 1
                progress.update(1)
        finally:
            if cm_pq is not None:
                cm_pq.__exit__(None, None, None)
    progress.close()
    log.info("Wrote %d transactions in %.1fs (%.0f tx/s)",
             tx_count, time.time() - t0, tx_count / max(0.01, time.time() - t0))

    # ------------------ 8. Persist account final balances + report ---------
    # Re-emit accounts with the post-simulation solde_actuel (the generator
    # has been updating account.solde_actuel in place).
    write_rows_csv(output_dir / "accounts.csv", ACCOUNT_FIELDS, (a.to_row() for a in accounts))

    locale_counts = Counter(c.locale_code for c in customers)
    currencies = {get_locale(code).currency for code in locale_counts}
    report = {
        "seed": args.seed,
        "country": args.country,
        "currency": get_locale(args.country).currency if args.country != "mix" else sorted(currencies),
        "locale_distribution": {k: round(v / len(customers), 4) for k, v in sorted(locale_counts.items())},
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "counts": {
            "customers": len(customers),
            "accounts": len(accounts),
            "cards": len(cards),
            "subscriptions": len(subs),
            "loans": len(loans),
            "merchants": len(merchant_catalog),
            "transactions": tx_count,
        },
        "target_transactions": args.target_transactions,
        "elapsed_seconds": round(time.time() - t_global, 2),
        "formats": sorted(formats),
        "bank_presets": preset_ids,
        "profile_distribution_observed": {},
        "profile_distribution_by_preset": {},
        "trajectory_stats": {},
        "files": {
            "customers": str(output_dir / "customers.csv"),
            "accounts":  str(output_dir / "accounts.csv"),
            "cards":     str(output_dir / "cards.csv"),
            "subscriptions": str(output_dir / "subscriptions.csv"),
            "loans":     str(output_dir / "loans.csv"),
            "merchants": str(output_dir / "merchants.csv"),
            "transactions_csv": str(tx_csv_path) if use_csv else None,
            "transactions_parquet": str(tx_parquet_path) if tx_parquet_path else None,
            "categories": "categories.json",
        },
    }
    # observed profile mix (global + per bank preset)
    obs = Counter(c.profil for c in customers)
    report["profile_distribution_observed"] = {k: round(v / len(customers), 4) for k, v in obs.items()}
    by_preset: dict[str, Counter] = defaultdict(Counter)
    for c in customers:
        by_preset[c.bank_preset or "_none"][c.profil] += 1
    report["profile_distribution_by_preset"] = {
        pid: {prof: round(cnt / sum(cc.values()), 4) for prof, cnt in sorted(cc.items())}
        for pid, cc in sorted(by_preset.items())
    }

    # trajectory stats: prove behavioural variance increased
    trajs = list(trajectories_by_customer.values())
    if trajs:
        phase_counts = [len(t.phases) for t in trajs]
        init_incomes = [t.phases[0].monthly_income for t in trajs]
        final_incomes = [
            next((p.monthly_income for p in reversed(t.phases) if p.status == "active"),
                 t.phases[0].monthly_income)
            for t in trajs
        ]
        transitions = Counter(p.transition for t in trajs for p in t.phases if p.transition != "init")
        report["trajectory_stats"] = {
            "customers_with_trajectory": len(trajs),
            "phases_per_customer_mean": round(statistics.fmean(phase_counts), 3),
            "phases_per_customer_max": max(phase_counts),
            "customers_with_transition": sum(1 for n in phase_counts if n > 1),
            "deceased_customers": sum(1 for t in trajs if any(p.status == "deceased" for p in t.phases)),
            "dormant_customers": sum(1 for t in trajs if any(p.status == "dormant" for p in t.phases)),
            "income_std_initial": round(statistics.pstdev(init_incomes), 2),
            "income_std_final": round(statistics.pstdev(final_incomes), 2),
            "terminal_rejection_fee_tx": terminal_rejection_fees,
            "transition_counts": dict(transitions.most_common()),
        }

    (output_dir / "generation_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    log.info("Generation done in %.1fs", time.time() - t_global)
    log.info("Report: %s", output_dir / "generation_report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
