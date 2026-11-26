# Forecasting daily bikeshare demand: what an honest evaluation shows

## Results

Train 2011, validation H1 2012 (182 days), test H2 2012 (184 days), split by
date. "Before" is the starter's 14 features (`reports/metrics_before.json`);
"after" adds my feature `cnt_roll_28`, the mean of the previous 28 days
(`reports/metrics.json`, produced by `make all`). The 28-day warm-up removes
42 early-2011 training rows (348 -> 306), which is why the mean baseline
moves even though it uses no features.

| Model | Features | Valid R^2 | Valid MAE | Test R^2 | Test MAE |
|---|---|---|---|---|---|
| baseline_mean | before | -0.9318 | 2002.2 | -2.1441 | 2847.7 |
| baseline_persistence | before | 0.4507 | 900.6 | 0.5099 | 840.1 |
| ridge | before | 0.6475 | 832.9 | 0.5833 | 947.1 |
| hgb | before | 0.2185 | 1296.6 | -0.4975 | 1972.6 |
| baseline_mean | after | -0.6894 | 1877.3 | -1.7717 | 2659.6 |
| baseline_persistence | after | 0.4507 | 900.6 | 0.5099 | 840.1 |
| ridge | after | 0.6839 | 777.5 | 0.6239 | 879.3 |
| hgb | after | 0.2415 | 1296.6 | -0.46 | 1952.4 |

R^2 is computed against each period's own mean, so 0 means "as good as a
constant nobody could have known in advance". For reference, the naive model
from Step 3, linear regression on `casual` and `registered`, scores test
R^2 = 1.000 (`python -m src.leakage_demo`); it is invalid and not in the table.

## Headline finding

The naive evaluation gives R^2 = 1.000 and is invalid: `casual + registered
== cnt` on every row (least-squares residual 7.3e-12), so that model learned
addition, not demand. Under a temporal split, predicting the 2011 mean for
late 2012 scores -1.77, because ridership grew about 73% and the
distribution moved. Ridge reaches 0.624 against a persistence baseline
("yesterday's count") of 0.510, but still loses to persistence on MAE (879
vs 840 rides). Gradient boosting scores -0.46 on test. It still beats the
mean baseline, so it is negative for a different reason: a tree cannot
predict above the largest value it trained on (6,043 rides), and 56.5% of
test days are above it. Negative R^2 and losing to a baseline are not the
same thing. Ridge is positive and only modestly ahead of persistence; hgb is
negative and well ahead of the mean. My feature, `cnt_roll_28`, raised
validation R^2 for ridge from 0.6475 to 0.6839, and for hgb from 0.2185 to
0.2415. On the same 306 training rows the gains are +0.038 and +0.049, so
they are not an artefact of the shorter training window. I kept it.

## Exercise 4: target transformation

Gradient boosting loses to ridge because a tree cannot predict a value above
the largest target it saw in training (6,043 rides in 2011), and 56.5% of
test days are above that. So I changed what the models predict: instead of
`cnt`, they predict `cnt - cnt_roll_28`, today's gap from the previous 28
days, and `cnt_roll_28` is added back to score on the ride scale. The gap
stays inside the training range as ridership grows, so the tree no longer
has to extrapolate. `cnt_roll_28` is already shifted, so it is known at
prediction time. The code is `fit_and_score_diff()` in `src/train.py`, run
with `python -m src.train --target-diff`. It never writes
`reports/metrics.json`, which stays untransformed.

I chose the transformation on the validation set, comparing three candidates
with both models:

| Target | ridge valid R^2 | hgb valid R^2 |
|---|---|---|
| `cnt` (untransformed) | 0.6839 | 0.2415 |
| `cnt - cnt_roll_28` | 0.6932 | 0.6950 |
| `cnt / cnt_roll_28` | 0.4039 | 0.6754 |
| `log(cnt)` | 0.3740 | 0.1840 |

Then I looked at the test set once, for the chosen transformation only
(`--target-diff --final`):

| Model | Target | Test R^2 | Test MAE |
|---|---|---|---|
| ridge | `cnt` | 0.6239 | 879.3 |
| ridge | `cnt - cnt_roll_28` | 0.6350 | 856.7 |
| hgb | `cnt` | -0.4600 | 1952.4 |
| hgb | `cnt - cnt_roll_28` | 0.6335 | 731.8 |
| persistence | (none) | 0.5099 | 840.1 |

**Is it defensible?** I think the difference target is, and the ratio target
is not. The difference target helps both models, ridge slightly (+0.009 on
validation) and hgb a lot (+0.45). It does not hide the growth trend: it
makes it explicit, by asking each model only for the deviation from a level
that already contains the growth. The ratio target rescues hgb but drops
ridge from 0.68 to 0.40, so choosing it would mean picking the transformation
that favours one model, which is winning the comparison rather than making
it fair. On test, the difference target closes the gap: hgb goes from -0.46
to 0.63, level with ridge (0.635). It is also the only model here that beats
persistence on MAE (732 vs 840). The original finding still stands:
untransformed trees cannot extrapolate a growing series. The transformation
fixes that by removing the need to extrapolate, not by making trees
extrapolate.

## Exercise 5: ridge vs persistence

Ridge is worth deploying over "predict yesterday's count", because it avoids
the large misses that persistence makes, and on this test set the large
misses are where the money is. On H2 2012, ridge scores R^2 0.624 against
persistence's 0.510 and has a lower RMSE (1,068 vs 1,219 rides). It is off by
more than 2,000 rides on 10 days to persistence's 17, and its worst miss is
smaller (4,115 vs 4,470). Persistence fails exactly when demand changes
suddenly, because it repeats every shock one day late. After Hurricane Sandy
(22 rides on 2012-10-29) it predicted 22 for 10-30 (actual 1,096) and 1,096
for 10-31 (actual 5,566), a miss of 4,470 rides. Ridge predicted about 3,300
and 3,450 on those two days. Persistence does win on the typical day: its MAE
is lower (840 vs 879), its median error is 506 against ridge's 807, and it
is closer on 57% of days. Ridge also underpredicts by 427 rides on average,
because it learned 2011 demand levels and ridership kept growing. So the
case for ridge rests on its tail, not its typical day. For a system that has
to stage bikes and staff ahead of demand, a 4,000-ride miss costs more than
many 300-ride ones, which is why I would deploy ridge. Its bias should be
corrected first, for example by retraining on a rolling window of recent
data. Persistence remains the bar it has to keep beating.

## Attribution

**Model:** `qwen3.5:9b` via Ollama, built as `bikeshare-coder` with a 128k
context (raised from 64k on instructor guidance, with
`OLLAMA_KV_CACHE_TYPE=q8_0`). I did not switch agent models. I did switch
machines: Steps 1-2 ran on a CPU-only laptop (~6 tokens/s), everything after
on a desktop with an RTX 3080 Ti (~93 tokens/s), same model and context.
Separately, I used Claude Opus 5.5 in Claude Code for VS Code as a helper:
to check the local agent's output against printed numbers, and to write the
pieces listed below. It was not the tutorial agent, and its work is listed
separately so the two are not confused.

**Generated by the local agent (`bikeshare-coder`):**
- `cnt_roll_28` in `src/features.py` (via `/new-feature`), including
  decoupling `cnt_lag_7` and `cnt_roll_7` from `LAG_WARMUP`.
- `test_encode_weather_rejects_unknown_label` in `tests/test_leakage.py`.
- The seeded-fault edits and fixes in Exercise 2 (faults 1-3, and the copy
  into `data/raw/` in fault 4).
- `reports/audit.jsonl` (`agent/audit.py`) and the `/leakage-auditor`
  findings quoted in `docs/AUDIT.md`.
- Rejected and not kept: a rewrite of `src/train.py` (Step 6), two drafts of
  the `cnt_roll_28` test, a first unclassified-column test, and a first
  Exercise 4 experiment that trained on the validation set.

**Written by Claude Opus (helper), reviewed by me:**
- `test_roll_28_is_mean_of_prior_28_days`, the final `LAG_WARMUP = 28`
  correction, the raw-column classification sets in `src/config.py` and the
  tests in `tests/test_contract.py`, the raw sha256 check (`src/ingest.py`,
  `RAW_SHA256`, `test_raw_file_is_unchanged`), `fit_and_score_diff()` in
  `src/train.py`, `.claude/skills/seed-fault/SKILL.md`, and the CLAUDE.md
  additions.
- Drafts of `docs/SEEDED_FAULTS.md`, `docs/AUDIT.md`, this report, and
  lines in `docs/DECISIONS.md`, from outputs I ran and checked.
- The verification analyses I relied on: the `days_since_2011` ablation
  (Step 3), the train/test range evidence and the ridge coefficients
  (Step 6), the same-rows check of the feature, and the Exercise 5 numbers.

From the starter, unchanged: the pipeline, the hook, the leakage auditor,
the batch auditor and the `/new-feature` skill.

**Decisions that were mine** (each is a dated line in `docs/DECISIONS.md`):
- **What to predict:** daily `cnt`, from features known before the day.
- **What counts as leakage:** `casual` and `registered`, kept out after
  verifying the identity myself; `cnt_2d_bfr` excluded as unverified, not as
  leakage; time indexes excluded, confirmed when `days_since_2011` drove
  the agent's model to R^2 -4.06 (Step 3).
- **How to split:** by date, test set used once per question and only after
  the choice was made on validation.
- **Which baselines:** mean and persistence, with persistence as the one
  that matters.
- **Whether the answer is believable:** rejecting the agent's R^2 1.000,
  -4.06, its rewritten `train.py`, and its hgb "R^2 0.9988" as artefacts
  rather than results.
- **My feature and whether to keep it:** `cnt_roll_28`, kept on validation
  evidence.
- **The classification and hash checks:** an allowlist for raw columns and
  a pinned raw-file hash (both proposed by Claude Opus; accepting them, and
  the trade-off that new columns fail loudly, was my call).
- **Exercise 4:** the difference target is defensible, the ratio target is
  not.
- **Exercise 5:** ridge over persistence, on large misses.
