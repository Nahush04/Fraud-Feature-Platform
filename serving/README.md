# fraud-serving

Real-time fraud-scoring Flask API: fetches an entity's feature vector from
the Redis online store, runs the trained XGBoost model, returns a score and
a per-stage latency breakdown.

## Install (local dev)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pip install -e ../feature_store   # reuses fstore.online.RedisOnlineStore
```

## Run locally

```bash
# Redis: docker compose -f ../infra/docker-compose.yml up -d redis
# model: fraud-train run --delta-path ... --model-dir ../model   (from training/)

export MODEL_DIR=../model
export REDIS_URL=redis://localhost:6379/0
flask --app serving.wsgi run --port 8080
```

```bash
curl -X POST http://localhost:8080/score \
    -H "Content-Type: application/json" \
    -d '{"card1": 7919, "TransactionAmt": 125.50}'
```

## API

| Endpoint | Purpose |
|---|---|
| `POST /score` | `{"card1": ..., "TransactionAmt": ...}` -> `{"score", "flagged", "entity_known", "latency_ms": {"feature_fetch", "inference", "total"}}` |
| `GET /healthz` | liveness -- never touches Redis or the model; a k8s liveness failure means "restart this pod" |
| `GET /readyz` | readiness -- pings Redis; a pod that can't reach the online store shouldn't get traffic |

`entity_known: false` for a `card1` the online store has never materialized
isn't an error — it's a legitimate cold-start case, scored with an all-null
feature row (the same state a genuinely-first transaction gets in training).

## Container

```bash
# from the repo root (needs feature_store/ and model/ as sibling build context)
docker build -f serving/Dockerfile -t fraud-serving:latest .
docker run -p 8080:8080 -e REDIS_URL=redis://host.docker.internal:6379/0 fraud-serving:latest
```

## Kubernetes (minikube)

```bash
minikube start
minikube addons enable metrics-server   # required for the HPA to see CPU usage
eval $(minikube docker-env)             # build directly into minikube's Docker
docker build -f serving/Dockerfile -t fraud-serving:latest ..

kubectl apply -f ../infra/k8s/redis.yaml
kubectl apply -f ../infra/k8s/configmap.yaml
kubectl apply -f ../infra/k8s/deployment.yaml
kubectl apply -f ../infra/k8s/service.yaml
kubectl apply -f ../infra/k8s/hpa.yaml

minikube service fraud-serving --url
```

## A real bug this surfaced

`build_feature_row` originally left a missing online feature (JSON `null`,
e.g. `email_txn_count_24h` for a transaction with no email) as Python `None`
in the single-row DataFrame. Pandas keeps that as `object` dtype rather than
`NaN`, and XGBoost rejects `object`-dtype columns outright — found by
actually running a trained model against a real request over real HTTP, not
by unit tests alone (a regression test now covers it directly). Fixed by
casting the row to `float64` after construction. See `docs/decisions.md`.

## Layout

```
src/serving/
  app.py     Flask app: /score, /healthz, /readyz
  model.py   load the training-produced model artifact, build the feature row
  wsgi.py    gunicorn entry point
tests/       pytest suite: fakeredis + a stub model for /score behavior,
             a real trained-and-reloaded XGBoost model for the model.py round trip
```

## Tests

```bash
pytest
```
