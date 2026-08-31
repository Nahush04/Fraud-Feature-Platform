# scripts

## end_to_end_demo.py

Runs the full pipeline's serving loop for real: a transaction scored by the
real trained model, flagged, notified into the review queue, and decided by
an analyst -- across two real running servers talking real HTTP, not test
clients.

```bash
cd scripts
../serving/.venv/Scripts/python.exe end_to_end_demo.py
```

Requires `data/feature_engineering_output` and `model/` to already exist
(`feature_engineering/README.md`, `training/README.md`). Starts a real
Django dev server and a real Flask dev server on throwaway ports, searches
the real materialized IEEE-CIS data for an (entity, amount) pair whose real
model score actually clears the real decision threshold (doesn't fabricate
one), sends it through, confirms it lands in the review queue, approves it,
confirms the audit trail, tears both servers down, and cleans up its
scratch sqlite db.

Exits non-zero (via an `assert`) if any step doesn't behave as expected --
this is a real check, not a demo that always prints success.
