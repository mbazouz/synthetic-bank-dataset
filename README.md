# Synthetic Banking Dataset Generator

[![CI](https://github.com/mbazouz/synthetic-bank-dataset/actions/workflows/ci.yml/badge.svg)](https://github.com/mbazouz/synthetic-bank-dataset/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)

Generates a 100% synthetic — yet realistic — retail banking dataset for AI
training, personalized banking advice, scoring, behavioral detection and sales
demos.

Everything runs **locally**, with no cloud service.

## Country / locale (`--country`)

The generator produces **naturalized** data per country: names, banks, account
types, merchants, currency, IBAN/account-number formats, and statement labels.

| `--country` | Currency | Accounts | Identifier | Example labels |
|---|---|---|---|---|
| `us` *(default)* | USD | `checking`, `savings`, `brokerage`, `ira`… | ABA routing + account no. | `DIRECT DEP`, `ACH RENT`, `OVERDRAFT FEE` |
| `uk` | GBP | `current_account`, `cash_isa`, `sipp`… | `GB…` IBAN (sort code) | `BACS SALARY`, `DD RENT`, `OVERDRAFT INTEREST` |
| `fr` | EUR | `compte_courant`, `livret_a`, `pea`… | `FR…` IBAN (mod-97) | `VIR SALAIRE`, `PRELV LOYER`, `FRAIS AGIOS` |
| `mix` | per customer | all | per customer | a blend of the three |

`mix` assigns a country **per customer** (bank, currency, merchants and labels
all coherent for that customer). The default country is **`us`**.

```bash
python -m bank_gen.main --country uk  --customers 500  --output ./output --seed 4242
python -m bank_gen.main --country mix --customers 2000 --output ./output --seed 4242
```

Taxonomy **values** are localized too: `category` (`groceries`, `dining`…),
`subcategory` (`rent`, `salary`, `mortgage`…), `profile` (`student`, `manager`…),
`risk_appetite` (`conservative`…), `customer_segment` and `family_situation`.
The internal logic stays on canonical tokens; translation happens at write time
(see `bank_gen/locales/en_display.py`).

> ℹ️ The output is **fully English**: both the raw column NAMES (`output/`) and
> the values are anglicized, whatever the country (only `--country fr` emits
> French values/merchants, always under English column headers). The
> **delivered format** (`delivery/`, contract v1) is likewise 100% English and
> normalized.

> To add a country, create a `bank_gen/locales/<code>.py` exposing a `LOCALE`
> object (use `bank_gen/locales/fr.py` as a template) and register it in
> `get_locale`.

## Quickstart

> **Important — 2 output formats:**
>
> 1. **`output/`** = **raw business** format (rich: `first_name`, `last_name`,
>    `monthly_income`, `risk_appetite`, `current_balance`...). Useful for sales
>    demos, internal analytics, training proprietary models.
>
> 2. **`delivery/<bank-id>/`** = **contract v1** format (normalized: `first_name`,
>    `last_name`, `annual_income_eur`, stable integer IDs, S3-mirror layout
>    `full/<cutoff>/` + `delta/<date>/`). **This is the format that passes
>    `make validate` and is ingestible by a downstream analytics pipeline.**
>
> To go from raw to contract, run `make deliver` after `make generate`. The
> `make ship` target chains both + validates locally.

> 📅 **Dates should end "today".** By default (no `--start`/`--end`), the
> generator produces an **evergreen** window: the last ~3 years up to
> `date.today()` (see `DEFAULT_END_DATE`/`DEFAULT_START_DATE` in
> `bank_gen/config.py`). This is deliberate: an analytics pipeline that computes
> "recent" signals over `now()`-anchored windows (e.g. the last 365 days) **will
> see nothing if the dataset stops in the past.** See [§ Dates & freshness](#dates--freshness).

```bash
cd synthetic-bank-dataset

# Option A — Docker (recommended: no Python/pip/venv needed on the host):
docker run --rm -v "$PWD":/work -w /work python:3.12-slim bash -c '
  pip install -q -r requirements.txt
  python -m bank_gen.main    --customers 500 --output ./output --seed 4242
  python -m bank_gen.deliver --output ./output --delivery ./delivery \
                             --bank-id my-bank --cutoff "$(date +%F)"
'
# → delivery/my-bank/full/<today>/{customers,accounts,transactions}.csv (contract v1)

# Option B — local venv + Makefile (if python3-venv + pip available):
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# IMPORTANT: the Makefile has its own FIXED date defaults (START/END/CUTOFF) —
# override them with recent dates, otherwise stale data → empty recent features.
make ship CUSTOMERS=500 BANK_ID=my-bank END="$(date +%F)" CUTOFF="$(date +%F)" DELTAS=""
# → output/ (raw) + delivery/my-bank/full/<cutoff>/ (contract v1) + local validation

# Option C — Direct python (uses the default evergreen window):
python -m bank_gen.main    --customers 500 --output ./output --seed 4242
python -m bank_gen.deliver --output ./output --delivery ./delivery \
                           --bank-id my-bank --cutoff "$(date +%F)"

# Large target run (5M transactions, ~60k customers, 3 rolling years):
python -m bank_gen.main --customers 60000 --output ./output --seed 4242 --format csv,parquet
```

> ⚠️ **Common pitfall:** running only `python -m bank_gen.main` produces
> `output/` (raw format, NOT contract-v1 compliant). If you drop those files into
> the ingestion bucket, the validator will reject them (raw schema ≠ contract
> schema: unknown columns, missing contract columns). Run `make deliver` (or just
> `make ship`) afterward to get the consumable format.

### Dates & freshness

| Path | Default window | For recent data |
|---|---|---|
| `python -m bank_gen.main` (no `--start/--end`) | **evergreen**: `today-3y` → `today` | nothing to do ✅ |
| `make generate` / `make ship` | **fixed**: Makefile `START`/`END` (`2023-…`) | override `END="$(date +%F)" CUTOFF="$(date +%F)" DELTAS=""` |
| explicit `--start/--end` | whatever you pass | set `--end "$(date +%F)"` |

The `deliver` `--cutoff` is the boundary of the **full load** ingested at
onboarding; set it to today (`"$(date +%F)"`) so history runs up to now. The
optional `--deltas` are only used for later incremental syncs.

## Output

### Raw business format (`output/`)

| File | Contents |
|---|---|
| `customers.csv` | Customers (profile, segment, income, wealth, score, city, family situation...) |
| `accounts.csv` | Accounts (current, savings, retirement, investment, joint, business) with valid IBAN/routing/sort-code per locale |
| `cards.csv` | Visa/Mastercard cards (Luhn-valid, masked PAN) with limits and expiry |
| `subscriptions.csv` | Subscriptions (telecom, streaming, utilities, insurance, pro tools...) |
| `loans.csv` | Loans (mortgage, auto, consumer, personal, revolving) with outstanding balance |
| `merchants.csv` | Merchant catalogue (MCC, category, subcategory, amount ranges) |
| `transactions.csv` | The bulk — daily flow with salaries, rent, subscriptions, spending, ATM withdrawals, overdraft fees, internal transfers, life events |
| `transactions.parquet` | Same content, columnar format (snappy-compressed) with `--format parquet` |
| `categories.json` | Frozen taxonomy (categories, subcategories, transaction types, channels) |
| `generation_report.json` | Run metadata (volumes, duration, country/currency, observed profile distribution) |

### Contract v1 format (`delivery/<bank-id>/`)

The canonical column spec lives in [`bank_gen/deliver.py`](bank_gen/deliver.py)
(`CUSTOMER_V1_FIELDS`, `ACCOUNT_V1_REQUIRED`/`ACCOUNT_V1_OPTIONAL`,
`TRANSACTION_V1_REQUIRED`/`TRANSACTION_V1_OPTIONAL`). In short:

- **customers**: `id, first_name, last_name, email, phone, iban, address, postal_code, city, dob, annual_income_eur`
- **accounts**: required `id, customer_id, iban, opened_at, type` · optional `balance_current, overdraft_limit`
- **transactions**: required `id, account_id, customer_id, date, amount, label, category` · optional `balance_after_transaction, is_cash_withdrawal, is_subscription, is_salary, is_transfer, mcc`

```
delivery/<bank-id>/
  full/<cutoff>/
    customers.csv      11 columns (id, first_name, …, annual_income_eur)
    accounts.csv       5 required + 2 optional (balance_current, overdraft_limit)
    transactions.csv   7 required + 6 optional (is_subscription, mcc, balance_after_transaction…)
  delta/<delta_date>/
    transactions.csv   incremental delta (prev_cutoff < date ≤ delta_date)
```

`make deliver` converts raw → this format: schema mapping, synthetic generation
of the missing PII fields (email/phone/address — never real), stable
seed-deterministic integer IDs, full/delta partitioning by date.

## Architecture

```
bank_gen/
├── config.py           # Shared config: profile distribution, presets, defaults
├── locales/            # Per-country packs (fr/us/uk) + Locale/AccountRole/Labels
│   ├── __init__.py     #   Locale, AccountRole, Labels, get_locale resolver
│   ├── fr.py / us.py / uk.py
│   └── en_display.py   #   English value maps for the en_* locales
├── banking_utils.py    # IBAN (FR/GB) mod-97, US ABA routing, Luhn cards
├── profiles.py         # 10 archetypes: student / young_professional / family / manager / ...
├── merchants.py        # Per-locale merchant catalogues + noisy label variants
├── customers.py        # Customer generation (Faker per locale, weighted sampling)
├── accounts.py         # Multiple accounts per customer, by role
├── cards.py            # Cards per account (contactless, limits)
├── subscriptions.py    # Recurring subscriptions with possible churn
├── loans.py            # Loans with amortization and outstanding balance
├── life_events.py      # Marriage, birth, divorce, job loss, home purchase, raise, etc.
├── transactions.py     # **Core**: day-by-day streaming engine
├── io_writers.py       # CSV append-mode + Parquet by row groups (bounded memory)
└── main.py             # CLI orchestrator with tqdm
```

## Realism

- **Weighted profiles** (Student 10%, Young professional 18%, Family 22%, Manager 13%, High earner 6%, Freelancer 7%, Entrepreneur 3%, Investor 2%, Retiree 14%, Vulnerable 5%)
- **Income sampled per profile** (truncated normal), scaled to the locale's currency level
- **Wealth** = a multiple of income (long-tail for high earners/investors)
- **Valid account identifiers** per locale (FR/GB IBAN mod-97, US ABA routing checksum), **Luhn-valid PAN**, coherent fictitious BIC
- **Salaries** paid on the 25th-28th with ~4% sigma, bonus in March/December
- **Freelancers/entrepreneurs**: 1-3 client invoices per month, highly variable amounts
- **Rent** = profile ratio × income, inflation-indexed
- **Subscriptions**: popularity depends on profile (a retiree doesn't buy Game Pass, a student has a budget mobile plan)
- **Loans**: correctly computed monthly payments (amortization formula), coherent outstanding balance at period end
- **Daily spending**: Poisson(λ profile), weighted by category, profile-driven leisure bias
- **Seasonality**: travel in July/August, shopping in December/sales, back-to-school in September
- **Inflation**: per-country yearly rates applied to recurring amounts
- **Weekend boost**: restaurants/travel/shopping +60% on Sat/Sun
- **Time of day**: distinct peaks for dining (noon, 7-8pm), transport (8am, 6pm)
- **Label noise**: `WAL-MART`, `AMZN MKTP US`, `TESCO STORES`, `CARREFOUR CITY 75`, etc. (locale-specific)
- **Overdraft + fees**: if balance < -`overdraft_limit`, 25% chance of a fee
- **ATM withdrawals**: ~14% chance per day, discrete amounts (20, 50, 100...)
- **Internal savings transfer**: automatic on payday, rate per profile
- **Life events**: birth/marriage/divorce/relocation/car purchase/home purchase/job loss/major trip/financial incident — each durably changes income and activity

## Performance

- **Streaming** generation: transactions yielded one at a time, batched to disk in chunks of 100,000 rows.
- **Bounded** memory footprint regardless of transaction volume.
- Indicative timing on a modern laptop (see the volume table below):
  - 500 customers, 3 years → ~1-2 min, ~1.16M transactions
  - 60,000 customers, 3 years → ~1-2 h, ~140M transactions

## Compatibility

- Flat CSV → `psql \copy transactions FROM 'transactions.csv' CSV HEADER`
- Snappy Parquet → Spark/Polars/DuckDB/Pandas (`pd.read_parquet(...)`)
- UTF-8 everywhere, ISO 8601 dates, signed amounts in the dataset currency (negative = debit)

## Determinism

`--seed N` makes the whole run reproducible. Each customer has its own sub-seed,
so a single customer can be regenerated (`generate_transactions_for_customer`)
without replaying the entire dataset. (Note: the per-transaction `transaction_id`
is a random UUID, so it is the only column that varies between identical runs.)

## Notes on volume

A common brief asks for "~5M transactions for 50-120k customers" with "30-150
tx/month per customer". Those two constraints are **mathematically
incompatible**:
- 5M tx / 60k customers / 36 months = **2.3 tx/month/customer** (far below a real bank)
- 50 tx/month × 60k customers × 36 months = **108M transactions**

Design choice: we honor the **realistic density** (30-150 tx/month by profile)
and let the user calibrate `--customers`:

| `--customers` | Observed transactions (3 years) |
|---|---|
| 500   | ~1.16M |
| 2,000 | ~4.5M  ← **close to the 5M target** |
| 12,000 | ~28M |
| 60,000 | ~140M |

To hit exactly 5M: `--customers 2200`. For a heavy load benchmark, go up to 60k.

Observed tx/customer distribution (smoke test n=500):
- Students: ~660 tx over 3 years (~18/month)
- Vulnerable: ~1230 (~34/month) — many declined payments
- Young professionals: ~1825 (~50/month)
- Managers: ~2920 (~81/month)
- High earners: ~4400 (~122/month)
- Entrepreneurs: ~5680 (~158/month) — including the business account

## Consistency guarantees

- ❌ no transaction before the customer's `customer_since` date
- ❌ no transaction on an account before its `opened_at`
- ❌ no balance beyond `−1.3 × overdraft_limit` (payments past that are declined, and rejected direct debits emit a rejection-fee line + interest)
- ✅ `balance_after_transaction` is arithmetically exact per account
- ✅ spending amounts are scaled by `income / profile_income_mean` (a customer on 1200/month can't mechanically average a 200 basket at an electronics store)

## 100% synthetic data

All produced data is **entirely synthetic and fictitious**. Names, IBANs, card
numbers, merchants, addresses, emails and phone numbers are randomly generated
and do not correspond to any real person, account or institution.

## License

Distributed under the **Apache 2.0** license. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
