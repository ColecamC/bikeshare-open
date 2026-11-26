# Seeded faults

## Exercise 1: the failing test for `cnt_roll_28`, before the feature existed

Recorded 2026-11-25. `tests/test_leakage.py::test_roll_28_is_mean_of_prior_28_days`
was written first and run against the unchanged pipeline. It fails only on the
feature's absence, after its own checks (all 28 window days present in the raw
data; hand-computed mean 6716.142857) have passed.

```
python -m pytest tests/ -q
..........F....                                                          [100%]
================================== FAILURES ===================================
____________________ test_roll_28_is_mean_of_prior_28_days ____________________

feats =         dteday  instant  season  ...  cnt_lag_1 cnt_lag_7   cnt_roll_7
0   2011-01-10     10.0  WINTER  ...      822.0...    1787.0  1530.142857
713 2012-12-31    731.0  WINTER  ...     1796.0     920.0  1531.428571

[714 rows x 28 columns]

    def test_roll_28_is_mean_of_prior_28_days(feats):
        """cnt_roll_28 on 2012-06-15 = mean of raw cnt on 2012-05-18..2012-06-14.

        Availability: every input is from a day strictly before d, so it is known
        at prediction time. The day's own count (7665) must not be in the window.
        """
        raw = load_raw().set_index("dteday")[TARGET]
        d = pd.Timestamp("2012-06-15")
        window = pd.date_range(d - pd.Timedelta(days=28), d - pd.Timedelta(days=1))
        missing = [w.date() for w in window if w not in raw.index]
        assert not missing, f"window days absent from raw data: {missing}"
        expected = raw[window].mean()
        assert expected == pytest.approx(6716.142857)  # hand-computed from raw CSV
>       assert "cnt_roll_28" in feats.columns, "cnt_roll_28 not built by build_features()"
E       AssertionError: cnt_roll_28 not built by build_features()
E       assert 'cnt_roll_28' in Index(['dteday', 'instant', 'season', 'yr', 'mnth', 'holiday', 'weekday',\n       'temp', 'atemp', 'hum', 'windspeed', ...kday', 'month_sin', 'month_cos',\n       'weather_severity', 'cnt_lag_1', 'cnt_lag_7', 'cnt_roll_7'],\n      dtype='str')
E        +  where Index(['dteday', 'instant', 'season', 'yr', 'mnth', 'holiday', 'weekday',\n       'temp', 'atemp', 'hum', 'windspeed', ...kday', 'month_sin', 'month_cos',\n       'weather_severity', 'cnt_lag_1', 'cnt_lag_7', 'cnt_roll_7'],\n      dtype='str') =         dteday  instant  season  ...  cnt_lag_1 cnt_lag_7   cnt_roll_7\n0   2011-01-10     10.0  WINTER  ...      822.0...    1787.0  1530.142857\n713 2012-12-31    731.0  WINTER  ...     1796.0     920.0  1531.428571\n\n[714 rows x 28 columns].columns

tests\test_leakage.py:77: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_leakage.py::test_roll_28_is_mean_of_prior_28_days - Asserti...
1 failed, 14 passed in 2.24s
make: *** [Makefile:16: test] Error 1
```

<!-- Exercise 2 sections go below: three seeded faults, then the cp into data/raw/. -->

# Exercise 2: seeded faults

Each fault was planted by the local agent (`bikeshare-coder`, qwen3.5:9b) in
one session, so the PostToolUse hook fired on its edit. The fix was then
requested in a fresh session (`/clear`) with only "make test is failing".

## Fault 1: a forbidden column added to `feature_columns`

**The change** (`src/features.py`, `feature_columns()`):

```diff
-    return [c for c in numeric if c not in FORBIDDEN]
+    return [c for c in numeric if c not in FORBIDDEN] + ["casual"]
```

**Hook stderr** (PostToolUse, exit 2, returned to the agent immediately after its edit):

```
PostToolUse:Edit hook blocking error from command: "${CLAUDE_PROJECT_DIR}/.claude/hooks/check_leakage.sh": [${CLAUDE_PROJECT_DIR}/.claude/hooks/check_leakage.sh]: Leakage tests failed after editing C:/Users/colem/Desktop/work/bikeshare-open/src/features.py:
feats =         dteday  instant  season      yr  ... cnt_lag_1 cnt_lag_7   cnt_roll_7  cnt_roll_28
0   2011-01-31     31.0  WI...429
671 2012-12-31    731.0  WINTER  2012.0  ...    1796.0     920.0  1531.428571  3969.428571

[672 rows x 29 columns]

    def test_no_forbidden_features(feats):
        """Guards the gate, not the data: feature_columns() excludes FORBIDDEN by
        construction, so this cannot discover a *new* leaky column. What it
        catches is someone editing feature_columns() or FORBIDDEN -- which is
        exactly the fault the Step 7 hook demonstrates."""
        cols = set(feature_columns(feats))
>       assert not (cols & FORBIDDEN), f"forbidden columns in feature set: {cols & FORBIDDEN}"
E       AssertionError: forbidden columns in feature set: {'casual'}
E       assert not ({'atemp', 'casual', 'cnt_lag_1', 'cnt_lag_7', 'cnt_roll_28', 'cnt_roll_7', ...} & {'casual', 'cnt', 'cnt_2d_bfr', 'days_since_2011', 'instant', 'registered', ...})

tests\test_leakage.py:31: AssertionError
====================================== short test summary info ======================================
FAILED tests/test_leakage.py::test_no_forbidden_features - AssertionError: forbidden columns in fea...
1 failed, 7 passed in 0.80s
```

**`make test` output:**

```
python -m pytest tests/ -q
..........F.........                                                     [100%]
================================== FAILURES ===================================
_________________________ test_no_forbidden_features __________________________

feats =         dteday  instant  season  ...  cnt_lag_7   cnt_roll_7  cnt_roll_28
0   2011-01-31     31.0  WINTER  ...     141....142857  4071.321429
671 2012-12-31    731.0  WINTER  ...      920.0  1531.428571  3969.428571

[672 rows x 29 columns]

    def test_no_forbidden_features(feats):
        """Guards the gate, not the data: feature_columns() excludes FORBIDDEN by
        construction, so this cannot discover a *new* leaky column. What it
        catches is someone editing feature_columns() or FORBIDDEN -- which is
        exactly the fault the Step 7 hook demonstrates."""
        cols = set(feature_columns(feats))
>       assert not (cols & FORBIDDEN), f"forbidden columns in feature set: {cols & FORBIDDEN}"
E       AssertionError: forbidden columns in feature set: {'casual'}
E       assert not ({'atemp', 'casual', 'cnt_lag_1', 'cnt_lag_7', 'cnt_roll_28', 'cnt_roll_7', ...} & {'casual', 'cnt', 'cnt_2d_bfr', 'days_since_2011', 'instant', 'registered', ...})

tests\test_leakage.py:31: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_leakage.py::test_no_forbidden_features - AssertionError: fo...
1 failed, 19 passed in 2.30s
make: *** [Makefile:16: test] Error 1
```

**Turns to fix:** 1 prompt, 6 tool calls (`make test` -> read `src/config.py`
-> grep `feature_columns` -> read `src/features.py` -> edit -> `make test`,
20 passed). It removed exactly the seeded `+ ["casual"]`, and the file is
identical to its pre-fault version.

Caveat: the agent never ran `git log`, but it cited the commit message
"Seed fault 1: casual added to feature_columns", which Claude Code puts in
the session context at startup. The fault was named in its context, so the
turn count is a lower bound. For faults 2 and 3 the broken state was not
committed before the fix session.

## Fault 2: `.shift(1)` deleted from `cnt_roll_7`

**The change** (`src/features.py`, `build_features()`):

```diff
-    out["cnt_roll_7"] = out[TARGET].shift(1).rolling(7).mean()
+    out["cnt_roll_7"] = out[TARGET].rolling(7).mean()
```

Without the shift, the 7-day mean on day d includes d's own count, so the
feature contains part of the target.

**Hook stderr** (PostToolUse, exit 2, returned to the agent immediately after its edit):

```
PostToolUse:Edit hook blocking error from command: "${CLAUDE_PROJECT_DIR}/.claude/hooks/check_leakage.sh": [${CLAUDE_PROJECT_DIR}/.claude/hooks/check_leakage.sh]: Leakage tests failed after editing C:/Users/colem/Desktop/work/bikeshare-open/src/features.py:
[672 rows x 29 columns]

    def test_rolling_mean_excludes_today(feats):
        """cnt_roll_7 must be the mean of the 7 calendar days *before* today."""
        by_date = feats.set_index("dteday")[TARGET]
        date = feats.dteday.iloc[200]
        window = [date - pd.Timedelta(days=k) for k in range(1, 8)]
        if all(d in by_date.index for d in window):
            expected = sum(by_date[d] for d in window) / 7
>           assert feats.set_index("dteday").cnt_roll_7[date] == pytest.approx(expected)
E           assert np.float64(4605.285714285715) == 4724.428571428572 � 0.00472443
E             
E             comparison failed
E             Obtained: 4605.285714285715
E             Expected: 4724.428571428572 � 0.00472443

tests\test_leakage.py:57: AssertionError
====================================== short test summary info ======================================
FAILED tests/test_leakage.py::test_rolling_mean_excludes_today - assert np.float64(4605.28571428571...
1 failed, 7 passed in 0.85s
```

**`make test` output:**

```
python -m pytest tests/ -q
.............F......                                                     [100%]
================================== FAILURES ===================================
______________________ test_rolling_mean_excludes_today _______________________

feats =         dteday  instant  season  ...  cnt_lag_7   cnt_roll_7  cnt_roll_28
0   2011-01-31     31.0  WINTER  ...     141....428571  4071.321429
671 2012-12-31    731.0  WINTER  ...      920.0  1789.857143  3969.428571

[672 rows x 29 columns]

    def test_rolling_mean_excludes_today(feats):
        """cnt_roll_7 must be the mean of the 7 calendar days *before* today."""
        by_date = feats.set_index("dteday")[TARGET]
        date = feats.dteday.iloc[200]
        window = [date - pd.Timedelta(days=k) for k in range(1, 8)]
        if all(d in by_date.index for d in window):
            expected = sum(by_date[d] for d in window) / 7
>           assert feats.set_index("dteday").cnt_roll_7[date] == pytest.approx(expected)
E           assert np.float64(4605.285714285715) == 4724.428571428572 ± 0.00472443
E             
E             comparison failed
E             Obtained: 4605.285714285715
E             Expected: 4724.428571428572 ± 0.00472443

tests\test_leakage.py:57: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_leakage.py::test_rolling_mean_excludes_today - assert np.fl...
1 failed, 19 passed in 2.34s
make: *** [Makefile:16: test] Error 1
```

**Turns to fix:** 0 extra prompts. The agent was told to make the edit and
then stop without fixing anything, but when the hook's stderr reached it, it
read `src/features.py`, restored `.shift(1)`, and ran the leakage tests and
then the full suite, all in the same turn (1 read, 1 edit, 2 test runs). So
the hook did what it is for: the agent could not carry on as if the edit
were fine. Because it reverted the fault before anyone could run
`make test`, the output above was captured by re-applying the same one-line
change by hand and restoring it immediately afterwards.

