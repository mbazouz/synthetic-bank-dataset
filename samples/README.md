# Sample output

A tiny, ready-to-look-at slice of generated data (US locale), so you can see the
shape of the output without running anything.

Generated with:

```bash
python -m bank_gen.main --country us --customers 12 --seed 4242 \
    --start 2024-01-01 --end 2024-03-31 --output ./output
```

- `customers.csv` — 12 customers
- `accounts.csv` — their accounts
- `transactions.csv` — the first 300 transactions (the real run produces a few thousand)

All data is 100% synthetic. Generate your own with any `--country` (fr/us/uk/mix),
size and date range — see the main [README](../README.md).
