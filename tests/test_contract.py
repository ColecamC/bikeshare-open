"""Guard rails on the ingest contract and the trained model's behaviour."""
import pandas as pd
import pytest
from sklearn.metrics import r2_score

from src.config import (ENCODED_COLS, FORBIDDEN, LAG_WARMUP, RAW_FEATURE_COLS,
                        TARGET, UNUSED_COLS)
from src.features import build_features, feature_columns, reindex_to_calendar
from src.ingest import load_raw
from src.train import MODELS, temporal_split


@pytest.fixture(scope="module")
def raw():
    return load_raw().sort_values("dteday").reset_index(drop=True)


@pytest.fixture(scope="module")
def feats(raw):
    return build_features(raw)


def test_calendar_is_complete_before_lagging(raw):
    """The reindexed frame must have no gaps, or the lags are wrong."""
    grid = reindex_to_calendar(raw)
    assert set(grid.dteday.diff().dropna().dt.days.unique()) == {1}


def test_only_expected_rows_are_dropped(raw, feats):
    """Rows may only vanish for the lag warm-up or downstream of a genuinely
    absent day -- never because an encoder produced a silent NaN.

    Accounting: the first LAG_WARMUP days have no complete history. Each
    absent calendar day m costs the LAG_WARMUP rows after it (cnt_lag_1 is
    NaN on m+1, cnt_roll_7 is NaN on m+1..m+7, cnt_lag_7 on m+7; their
    union is 7 rows). Day m itself was never in `raw`, so it is not a loss.
    The bound is exact for the current feature set; add a longer lag and
    LAG_WARMUP in src/config.py must grow with it.
    """
    full = pd.date_range(raw.dteday.min(), raw.dteday.max(), freq="D")
    missing_days = len(full) - len(raw)
    allowed_loss = LAG_WARMUP + LAG_WARMUP * missing_days
    lost = len(raw) - len(feats)
    assert lost <= allowed_loss, f"lost {lost} rows; expected at most {allowed_loss}"


def test_beats_the_mean_baseline(feats):
    """A model that cannot beat predicting the training mean is not a result."""
    cols = feature_columns(feats)
    train, _, test = temporal_split(feats)
    ridge = MODELS["ridge"]
    ridge.fit(train[cols], train[TARGET])
    assert r2_score(test[TARGET], ridge.predict(test[cols])) > 0.4


def test_persistence_baseline_is_reported():
    """The baseline that matters for a lag-driven model is 'yesterday again'.
    It must be in the comparison, whatever its score."""
    assert "baseline_persistence" in MODELS


CLASSIFIED = FORBIDDEN | RAW_FEATURE_COLS | ENCODED_COLS | UNUSED_COLS | {"dteday"}


def unclassified(columns):
    """Raw columns that src/config.py does not account for.

    Checked against explicit sets, never against feature_columns():
    feature_columns() admits any new numeric column, so a column that is
    already in the feature set is not evidence that anyone classified it.
    """
    return sorted(set(columns) - CLASSIFIED)


def test_every_raw_column_is_classified(raw):
    """A new column in bike_daily.csv cannot enter the pipeline silently."""
    missing = unclassified(raw.columns)
    assert not missing, f"unclassified raw columns: {missing}"


@pytest.mark.parametrize("make", [
    lambda r: r.assign(new_col=1.0),          # new numeric column
    lambda r: r.assign(new_label="x"),        # new text column
    lambda r: r.rename(columns={"casual": "rider_mix"}),  # leak, renamed
], ids=["numeric", "text", "renamed_leak"])
def test_unclassified_catches_new_columns(raw, make):
    """The guard must flag a column whatever its dtype or name."""
    assert unclassified(make(raw).columns), "new column was not flagged"


def test_classification_sets_are_disjoint():
    """Each raw column has exactly one reason for being where it is."""
    sets = [FORBIDDEN, RAW_FEATURE_COLS, ENCODED_COLS, UNUSED_COLS]
    for i, a in enumerate(sets):
        for b in sets[i + 1:]:
            assert not (a & b), f"column classified twice: {sorted(a & b)}"


def test_raw_file_is_unchanged():
    """Raw data is immutable. Any change to its bytes -- an edit, a cp from
    Bash, a re-download from a mirror that moved -- fails here and in make data."""
    from src.config import RAW_SHA256
    from src.ingest import raw_sha256
    actual = raw_sha256()
    assert actual == RAW_SHA256, (
        f"data/raw/bike_daily.csv changed: sha256 {actual[:16]}..., expected {RAW_SHA256[:16]}...")
