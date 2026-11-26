"""Stage 3: temporal split, fit, evaluate, write metrics.

Two baselines and two models, on purpose.

  baseline_mean         predict the 2011 average for every day
  baseline_persistence  predict yesterday's count (cnt_lag_1)
  ridge                 standardised linear model on the audited features
  hgb                   gradient-boosted trees on the same features

The mean baseline shows what "the distribution moved" costs. Persistence
is the baseline that actually matters: ridge's features are dominated by
lagged demand, so if it cannot beat "yesterday again" it has learned
nothing worth reporting. The booster is there because it fails, and the
reason it fails is the headline result.

Run: python -m src.train
Exercise 4 experiment (prints only): python -m src.train --target-diff
"""
import json
import sys

import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.config import METRICS, PROCESSED, TARGET, TRAIN_END, VALID_END
from src.features import feature_columns


class PersistenceBaseline(BaseEstimator, RegressorMixin):
    """Predict a single lagged column unchanged. Nothing is fit."""

    def __init__(self, column: str = "cnt_lag_1"):
        self.column = column

    def fit(self, X, y=None):
        if self.column not in X.columns:
            raise ValueError(f"persistence baseline needs column {self.column!r}")
        return self

    def predict(self, X):
        return X[self.column].to_numpy(dtype=float)


MODELS = {
    "baseline_mean": DummyRegressor(strategy="mean"),
    "baseline_persistence": PersistenceBaseline("cnt_lag_1"),
    "ridge": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
    "hgb": HistGradientBoostingRegressor(random_state=0, max_iter=300),
}


def temporal_split(df: pd.DataFrame):
    """Split by date, never at random. A random split on a time series
    puts tomorrow in train and today in test."""
    train = df[df.dteday <= TRAIN_END]
    valid = df[(df.dteday > TRAIN_END) & (df.dteday <= VALID_END)]
    test = df[df.dteday > VALID_END]
    return train, valid, test


def fit_and_score() -> dict:
    df = pd.read_parquet(PROCESSED)
    cols = feature_columns(df)
    train, valid, test = temporal_split(df)

    results = {
        "n_features": len(cols),
        "features": cols,
        "n_train": len(train),
        "n_valid": len(valid),
        "n_test": len(test),
    }
    for name, model in MODELS.items():
        model.fit(train[cols], train[TARGET])
        results[name] = {
            split: {
                "r2": round(float(r2_score(part[TARGET], model.predict(part[cols]))), 4),
                "mae": round(float(mean_absolute_error(part[TARGET], model.predict(part[cols]))), 1),
            }
            for split, part in [("valid", valid), ("test", test)]
        }
    return results


def fit_and_score_diff(include_test: bool = False) -> dict:
    """Exercise 4: fit ridge and hgb on cnt - cnt_roll_28 instead of cnt.

    A tree cannot predict above the largest target it saw, and 2012 demand
    is above 2011's. The gap between today and the previous 28 days stays in
    range as ridership grows, so the booster can follow the trend. The same
    transform is applied to both models so the comparison stays fair.
    cnt_roll_28 is already shifted, so it is known at prediction time.

    Scores are on the cnt scale. Validation only, unless include_test is set
    for the single final look. Never writes reports/metrics.json.
    """
    df = pd.read_parquet(PROCESSED)
    cols = feature_columns(df)
    train, valid, test = temporal_split(df)
    parts = [("valid", valid)] + ([("test", test)] if include_test else [])
    results = {}
    for name in ("ridge", "hgb"):
        model = clone(MODELS[name]).fit(train[cols], train[TARGET] - train["cnt_roll_28"])
        results[f"{name}_diff"] = {}
        for split, part in parts:
            pred = model.predict(part[cols]) + part["cnt_roll_28"]
            results[f"{name}_diff"][split] = {
                "r2": round(float(r2_score(part[TARGET], pred)), 4),
                "mae": round(float(mean_absolute_error(part[TARGET], pred)), 1),
            }
    return results


if __name__ == "__main__":
    if "--target-diff" in sys.argv:
        # Experiment only: print, never overwrite the committed metrics.
        print(json.dumps(fit_and_score_diff(include_test="--final" in sys.argv), indent=2))
        sys.exit(0)
    res = fit_and_score()
    METRICS.parent.mkdir(parents=True, exist_ok=True)
    METRICS.write_text(json.dumps(res, indent=2))
    print(json.dumps({k: v for k, v in res.items() if k != "features"}, indent=2))
