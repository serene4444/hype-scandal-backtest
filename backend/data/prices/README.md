# Price data

The backtester reads one CSV per ticker from this folder: `META.csv`, `PLTR.csv`, and `SPY.csv` for the benchmark.

Each file needs a `date` column (YYYY-MM-DD) and a `close` column (daily closing price), one row per trading day:

```csv
date,close
2020-09-30,9.50
2020-10-01,9.46
```

The CSVs are git-ignored. The daily data job will write them here, and later they move into the Supabase `prices` table. Until then, `/backtests` and `/agent/rule` return 503 "Price data is not available yet".
