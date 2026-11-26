# Bikeshare demand capstone

Daily Capital Bikeshare counts, 2011-2012. We forecast `cnt` (total daily
rides) from calendar, weather, and lagged-demand features.

## Commands
- `make data` - download raw CSV and assert its shape
- `make features` - build `data/processed/features.parquet`
- `make train` - fit models, write `reports/metrics.json`
- `make test` - pytest; run this before claiming anything works
- `make all` - the three pipeline stages in order; reproduces every number
  in `reports/metrics.json` and the REPORT.md Results table
- `python -m src.train --target-diff` - Exercise 4 experiment (target
  `cnt - cnt_roll_28`), validation only; never writes `reports/metrics.json`

## Non-negotiable rules
- **Never** put `casual` or `registered` in a feature set:
  `casual + registered == cnt` exactly. `src/config.py` lists these and the
  other excluded columns (`cnt_2d_bfr`, raw time indexes) with the reason
  for each. Derive feature lists from `FORBIDDEN`; never hand-type them.
- **Never** split this data randomly. Use `src.train.temporal_split`.
  Train = 2011, valid = H1 2012, test = H2 2012. Never tune on test.
- Any new lag or rolling feature must be built on a gap-free calendar
  index (`src.features.reindex_to_calendar`) and must `.shift(1)` before
  it aggregates. Add a test for it in `tests/test_leakage.py`.
- `LAG_WARMUP` must equal the longest window (28, for `cnt_roll_28`); the
  row-loss test depends on it. Never use it as a window size.
- **Never** change `data/raw/bike_daily.csv` by any means: no edit, copy,
  or re-download. Its sha256 is pinned (`RAW_SHA256`); `make data` and
  `make test` fail on any change. Fix data problems downstream, in code.
- Every raw column must be classified in `src/config.py` (`FORBIDDEN`,
  `RAW_FEATURE_COLS`, `ENCODED_COLS` or `UNUSED_COLS`). A new column fails
  `tests/test_contract.py` until someone decides which it is.
- Report the mean baseline **and** the persistence baseline (yesterday's
  count) alongside every model. A negative R^2 is a finding, not a bug
  to hide.

## Skills
- `/new-feature <idea>` - add a feature, test first, report validation delta
- `/seed-fault <description>` - break one thing, record what catches it, restore

## Style
- Standard library, pandas, scikit-learn only. No new dependencies
  without asking. Versions are pinned in `requirements.txt`.
- Modules are runnable: `python -m src.<module>` prints a one-line `OK ...`
  summary.
- Paths and constants live in `src/config.py`. Nothing is hardcoded twice.

## Gotchas
- The mirror in `DATA_URL` is missing 2011-03-10. It is NOT the UCI file:
  728 rows from 2011-01-03, not 731 from 2011-01-01.
- `weather` uses the labels `GOOD` / `MISTY` / `BAD`, not the UCI codes 1-4.
- Ridership grew ~65% from 2011 to 2012, so tree models trained on 2011
  cannot extrapolate to 2012. That is the headline result, not an error.
- 2012-10-29 (Hurricane Sandy, 22 rides) is in the test set. Expect it in
  any residual plot.
