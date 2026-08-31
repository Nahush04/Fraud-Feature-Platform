"""Real-time fraud-scoring API.

    POST /score {"card1": 7919, "TransactionAmt": 125.50}
    -> {"score": 0.62, "flagged": true, "entity_known": true, "latency_ms": {...}}

/healthz is a liveness probe (process is up) and never touches Redis or the
model -- a k8s liveness probe failing should mean "restart this pod", not
"a downstream dependency is briefly unavailable". /readyz is the readiness
probe and does check Redis connectivity, since a pod that can't reach the
online store shouldn't receive traffic yet.
"""

from __future__ import annotations

import os
import time

import redis
from flask import Flask, jsonify, request

from fstore.online import RedisOnlineStore
from serving.model import build_feature_row, load_model


def create_app(redis_client=None, model=None, meta=None) -> Flask:
    app = Flask(__name__)

    app.config["redis_client"] = redis_client or redis.Redis.from_url(
        os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    )
    if model is None or meta is None:
        loaded_model, loaded_meta = load_model(os.environ.get("MODEL_DIR", "/app/model"))
        model = model or loaded_model
        meta = meta or loaded_meta
    app.config["model"] = model
    app.config["meta"] = meta

    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok"), 200

    @app.get("/readyz")
    def readyz():
        try:
            app.config["redis_client"].ping()
        except Exception as exc:  # noqa: BLE001 -- any Redis client error means "not ready"
            return jsonify(status="not ready", reason=str(exc)), 503
        return jsonify(status="ready"), 200

    @app.post("/score")
    def score():
        payload = request.get_json(silent=True) or {}
        entity_id = payload.get("card1")
        transaction_amt = payload.get("TransactionAmt")
        if entity_id is None or transaction_amt is None:
            return jsonify(error="card1 and TransactionAmt are required"), 400

        store = RedisOnlineStore(app.config["redis_client"])

        t0 = time.perf_counter()
        vector = store.read_vector(entity_id)
        t1 = time.perf_counter()

        features = build_feature_row(app.config["meta"], transaction_amt, vector)
        fraud_score = float(app.config["model"].predict_proba(features)[0][1])
        t2 = time.perf_counter()

        return jsonify(
            score=fraud_score,
            flagged=fraud_score >= app.config["meta"]["decision_threshold"],
            entity_known=vector is not None,
            latency_ms={
                "feature_fetch": round((t1 - t0) * 1000, 4),
                "inference": round((t2 - t1) * 1000, 4),
                "total": round((t2 - t0) * 1000, 4),
            },
        )

    return app
