# fraud-train

Trains an XGBoost fraud classifier on `feature_engineering`'s output, tracked
in MLflow, evaluated on a walk-forward (time-sliced, never shuffled) golden
holdout against a logistic-regression baseline.

## Why a time-sliced holdout, not a random split

A random train/test split would let the model train on transactions that
happen *after* some of the transactions it's tested on — the model would
never see that in production, where every transaction it scores is genuinely
in the future relative to its training data. `time_based_split` sorts by
`TransactionDT` and puts the earliest `1 - test_fraction` in train, the rest
in test, matching the walk-forward discipline used elsewhere in this
portfolio (see the Stock-Prediction-with-GANs backtest).

## Install

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pip install -e ../feature_store   # for load_training_frame's real Delta reads
```

## Use

```bash
fraud-train run --delta-path ../feature_engineering_output --test-fraction 0.2
```

Prints a side-by-side PR-AUC / ROC-AUC / F1 comparison between the baseline
and XGBoost, and the MLflow run IDs for both (`mlflow ui --backend-store-uri
sqlite:///mlruns.db` to browse them).

## Why the offline feature table doubles as the training frame

`feature_engineering`'s Delta output already carries `isFraud` through
unchanged (a static label needs no point-in-time joining) and each row's
features were already computed as of that exact transaction's time — so the
offline table *is* the training frame, with no separate join step.
`fstore.pit_join` is for the different case of labeling/scoring an event
that isn't already a row in that table.

## Layout

```
src/train/
  data.py       load offline features, walk-forward split, fixed feature-column selection
  baseline.py   logistic regression (median-imputed, class-weighted)
  pipeline.py   XGBoost (handles NaN features natively, scale_pos_weight for imbalance)
  evaluate.py   PR-AUC / ROC-AUC / F1-at-tuned-threshold, side-by-side report
  tracking.py   MLflow run wrapper (local sqlite backend by default)
  cli.py        fraud-train command-line entry point
tests/          pytest suite against a synthetic, deliberately-imbalanced,
                deliberately-separable dataset (tests/conftest.py) -- real
                model fits and real metric computation, not mocked
```

## Tests

```bash
pytest
```

14 tests: walk-forward split correctness, NaN-handling for both models
(baseline via imputation, XGBoost natively), class-imbalance weighting,
metric correctness against a known-separable synthetic dataset, and MLflow
run logging.

## A real bug this surfaced

MLflow 2.x's local filesystem tracking backend (`./mlruns`) is now in
maintenance mode and raises by default (`MLFLOW_ALLOW_FILE_STORE` opt-out
required) -- discovered when the test suite failed against a freshly
installed `mlflow`, not from reading changelogs. Fixed by defaulting to a
local sqlite backend (`sqlite:///mlruns.db`) instead, both in the CLI and in
tests (see `docs/decisions.md`).
