import fakeredis
import numpy as np
import pytest

from serving.app import create_app

META = {
    "feature_columns": ["TransactionAmt", "entity_txn_count_1h", "entity_amt_zscore"],
    "decision_threshold": 0.5,
}


class StubModel:
    """predict_proba returns a high fraud score whenever the request-provided
    TransactionAmt exceeds 1000 -- deterministic and inspectable, so tests can
    assert on exact scores without needing a real trained model.
    """

    def predict_proba(self, X):
        amt = X["TransactionAmt"].iloc[0]
        fraud_prob = 0.9 if amt > 1000 else 0.1
        return np.array([[1 - fraud_prob, fraud_prob]])


@pytest.fixture
def redis_client():
    return fakeredis.FakeStrictRedis()


@pytest.fixture
def app(redis_client):
    return create_app(redis_client=redis_client, model=StubModel(), meta=META)


@pytest.fixture
def client(app):
    return app.test_client()
