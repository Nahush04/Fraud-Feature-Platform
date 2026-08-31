# load_testing

Locust load test against `serving`'s `/score` endpoint, meant to be run
against the minikube-hosted deployment to observe HPA scaling and real
p50/p95/p99 latency under load.

## Install

```bash
pip install locust
```

## Get a real known-entity sample (optional but recommended)

```bash
python -c "
from fstore.offline import read_offline_features
df = read_offline_features('../data/feature_engineering_output')
print(','.join(str(x) for x in df['card1'].value_counts().head(50).index))
"
```

```bash
export LOAD_TEST_KNOWN_ENTITIES="<paste the comma-separated list here>"
```

## Run

```bash
minikube service fraud-serving --url   # get the URL first
locust -f locustfile.py --host <that-url>
```

Open the Locust web UI (default `http://localhost:8089`), set concurrent
users and spawn rate, start the run. Watch pod count scale with:

```bash
kubectl get hpa fraud-serving --watch
```

Save Locust's exported CSV/HTML report into `results/` (gitignored except
for a summary you choose to keep) and record the headline p50/p95/p99 and
observed pod-count-over-time in `../docs/benchmarks.md`.
