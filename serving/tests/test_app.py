class BrokenClient:
    def ping(self):
        raise ConnectionError("redis unreachable")


def test_healthz_never_touches_redis_or_the_model(app):
    app.config["redis_client"] = BrokenClient()  # even broken, /healthz must still say ok
    client = app.test_client()
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_readyz_ok_when_redis_reachable(client):
    resp = client.get("/readyz")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ready"


def test_readyz_fails_when_redis_unreachable(app):
    app.config["redis_client"] = BrokenClient()
    client = app.test_client()
    resp = client.get("/readyz")
    assert resp.status_code == 503


def test_score_requires_card1_and_transaction_amt(client):
    resp = client.post("/score", json={"card1": 100})
    assert resp.status_code == 400


def test_score_for_unknown_entity_returns_low_amount_score(client):
    resp = client.post("/score", json={"card1": "never-seen-before", "TransactionAmt": 20.0})
    body = resp.get_json()

    assert resp.status_code == 200
    assert body["entity_known"] is False
    assert body["score"] == 0.1
    assert body["flagged"] is False
    assert set(body["latency_ms"]) == {"feature_fetch", "inference", "total"}


def test_score_for_known_entity_with_high_amount_is_flagged(client, redis_client):
    from fstore.online import RedisOnlineStore

    RedisOnlineStore(redis_client).write_vector(
        7919, as_of=1000, features={"entity_txn_count_1h": 3, "entity_amt_zscore": 2.5}
    )

    resp = client.post("/score", json={"card1": 7919, "TransactionAmt": 5000.0})
    body = resp.get_json()

    assert body["entity_known"] is True
    assert body["score"] == 0.9
    assert body["flagged"] is True
