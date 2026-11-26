# Audit

## Setup

I did this assignment on my own, which the course allows, so there was no
teammate's branch to audit. I followed the rule the professor set for
group audits instead: the auditor must not have been in the session that
produced the work. The audit target is every change I made to the starter
(`git diff 22b2ef8 HEAD -- src/ tests/`, where `22b2ef8` is the unmodified
starter commit): the `cnt_roll_28` feature, `LAG_WARMUP` 7 -> 28, the
classification of every raw column, the raw-file hash check, the weather
encoder test and the Exercise 4 `--target-diff` experiment.

It was run in a fresh Claude Code session (after `/clear`), with no access
to the conversations that produced the changes:

```
Use the leakage-auditor subagent to audit the changes since the starter commit: the output of `git diff 22b2ef8 HEAD -- src/ tests/`. Report its findings verbatim.
```

The main agent launched `.claude/agents/leakage-auditor.md` as a subagent,
which ran in its own context on the same local model (`bikeshare-coder`,
qwen3.5:9b). It made 15 tool calls: it read `src/config.py`, ran the diff,
read `src/features.py`, `src/train.py`, `tests/test_leakage.py` and
`tests/test_split.py`, read `reports/metrics.json`, ran `pytest`,
`python -m src.train` and `make data`/`make features`/`make train`, and ran
two Python checks of its own.

A limitation to keep in mind: the reviewer has the same weights as the
author, so it shares the author's blind spots. What it does not share is
the conversation in which a mistake was rationalised.

## The auditor's findings, verbatim

All five checks have been verified. Let me provide a summary:

## Audit Findings

After reviewing the diff against the five specified checks and running the full pipeline, **all five checks pass**. Here's the verification for each:

### 1. Target Leakage ✅
- `LEAKAGE_COLS = {"casual", "registered", "cnt"}` is defined in `src/config.py` line 35
- `FORBIDDEN` includes leakage columns plus time indexes and unverified columns (line 50)
- Test `test_no_forbidden_features` verifies no forbidden columns appear in feature set
- Arithmetic identity `casual + registered == cnt` is explicitly tested in `test_leakage_identity_holds`

### 2. Temporal Ordering ✅
- `temporal_split` uses date-based splitting (lines 58-64 `src/train.py`)
- Train = ≤2011-12-31, Valid = H1 2012, Test = H2 2012
- Tests verify ordering: `test_splits_are_ordered_in_time` and `test_no_overlapping_dates`
- All transformers use `.fit(train[...])` then predict on valid/test separately

### 3. Calendar Gaps ✅
- `reindex_to_calendar` (lines 34-50 `src/features.py`) fills missing days including 2011-03-10
- All lag features use `.shift(1)` or `.shift(7)` **before** aggregation
- Test `test_lags_are_true_calendar_lags` verifies lags match calendar-day predecessors

### 4. Silent Row Loss ✅
- Only `.dropna()` removes rows after lagging
- Warmup period loss is exactly `LAG_WARMUP = 28` rows (line 77 `src/config.py`)
- Tests bound this: `test_only_expected_rows_are_dropped`, `test_calendar_is_complete_before_lagging`

### 5. Unreported Baseline ✅
- `baseline_mean` (dummy regressor) and `baseline_persistence` are both in `MODELS` (lines 50-55 `src/train.py`)
- Both are reported next to every model score in `reports/metrics.json`
- Persistence baseline is the critical one—it "embarrasses" other models by using yesterday's count

### Additional Validated Changes from Diff:

1. **RAW_SHA256 added** (`src/config.py`, `src/ingest.py`): Protects against silent raw data modification (fault 4)
2. **LAG_WARMUP updated to 28** (`src/config.py`): Correct value for rolling(28).mean() which produces first 28 NaNs
3. **cnt_lag_7 and cnt_roll_28 fixes** (`src/features.py`): Previously used `shift(LAG_WARMUP)` which was wrong; now correctly uses `shift(7)` and `shift(1).rolling(28)`
4. **Exercise 4 diff target** (`src/train.py --target-diff`): Ridge/HGB on `cnt - cnt_roll_28` to handle trend extrapolation problem

All changes maintain compliance with CLAUDE.md rules and no findings require fixes.

## My verdict

**None of the auditor's findings change a number.** It reported no
problems, and I agree that there is no leakage, the split is by date, and
both baselines are reported. Three of its supporting claims are wrong in
the details, though, and it missed nothing I would call a finding.

What I ran to check each claim:

- **Target leakage: agree.** `test_leakage_identity_holds` asserts
  `casual + registered == cnt` on every row (`tests/test_leakage.py:20-22`),
  and `test_no_forbidden_features` passes. I had already confirmed the
  identity independently: a least-squares fit of cnt on casual and registered
  gives coefficients 1.0 and 1.0 with a maximum residual of 7.3e-12
  (docs/DECISIONS.md, Step 3).
- **Temporal ordering: agree.** `temporal_split` splits by date, the
  scaler sits inside the ridge pipeline so it is fit on training rows only,
  and the three tests in `tests/test_split.py` pass.
- **Calendar gaps: agree with the conclusion, not the wording.** It says
  `reindex_to_calendar` "fills missing days". It inserts an empty row for
  2011-03-10; I checked that the reindexed table has 729 rows and that
  `cnt` on 2011-03-10 is NaN. The row and the lags that depend on it are
  then dropped. Nothing is filled in, which is the point.
- **Silent row loss: agree with the conclusion; its number is wrong.** It
  says the loss "is exactly `LAG_WARMUP = 28` rows". I ran
  `build_features(load_raw())`: 728 raw rows become 672, so **56** rows are
  lost, 28 for the warm-up and 28 after the 2011-03-10 gap. That is the bound
  `test_only_expected_rows_are_dropped` enforces (28 + 28 x 1). The test
  is right; the auditor's description of it is not.
- **Unreported baseline: agree.** `MODELS` contains
  `DummyRegressor(strategy="mean")` and `PersistenceBaseline("cnt_lag_1")`
  (`src/train.py`), and both rows are in `reports/metrics.json`.
- **"cnt_lag_7 and cnt_roll_28 fixes": partly wrong.** `cnt_roll_28` is
  new, so it never used `LAG_WARMUP`. The starter's `cnt_lag_7` and
  `cnt_roll_7` used `LAG_WARMUP` as their window, which would have turned
  them into 28-day features when the warm-up was raised; they now use a
  literal 7 (docs/DECISIONS.md, Exercise 1 result).

**What it did not flag, and why I agree:** `fit_and_score_diff()` can read
the test set, but only when `--final` is passed. It is never called by
`make all`, it never writes `reports/metrics.json`, and I used it once,
after choosing the transformation on validation (docs/DECISIONS.md,
Exercise 4). Its `python -m src.train` and `make train` runs regenerated
`reports/metrics.json`; I checked that the numbers were unchanged
(ridge test R^2 0.6239, hgb -0.46).

## Batch auditor on my own repo (Part 4)

`python agent/audit.py . --out reports/audit.jsonl` wrote:

```
{"repo": "bikeshare-open", "leakage": "none", "temporal_ok": true, "baseline_reported": true, "reproducible": true, "findings": [], "confidence": "high"}
```

It made 33 tool calls (it read all of `src/` and `tests/`, ran `make all`
and `make test`, checked the split dates and seeds, and ran
`fit_and_score()` twice to check reproducibility) before returning the
schema-enforced result. It never called its custom `check_identity` tool,
so its "no leakage" rests on reading code and running my tests, not on the
least-squares check. Nothing was flagged, so there was nothing to fix or
argue with.
