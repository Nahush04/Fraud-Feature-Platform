"""Locust load test against the /score endpoint, driving HPA scaling on
minikube (or any deployment of `serving`).

    locust -f load_testing/locustfile.py --host http://<minikube-ip>:<nodeport>

Mixes known entities (drawn from a real materialized set, see
`--known-entities`) with a fraction of never-seen entity IDs, since real
traffic is a mix of returning and brand-new cards and the two paths have
different feature-fetch behavior (a Redis hit vs. a miss).
"""

from __future__ import annotations

import os
import random

from locust import HttpUser, between, task

# Populated from a real `card1` sample (see load_testing/README.md) via
# LOAD_TEST_KNOWN_ENTITIES="7919,9500,15885,..."; falls back to a small
# synthetic set so this file still runs standalone for a smoke test.
KNOWN_ENTITIES = [
    int(x) for x in os.environ.get("LOAD_TEST_KNOWN_ENTITIES", "7919,9500,15885,12345,6789").split(",")
]


class FraudScoringUser(HttpUser):
    wait_time = between(0.05, 0.3)

    @task(9)
    def score_known_entity(self):
        card1 = random.choice(KNOWN_ENTITIES)
        self._score(card1)

    @task(1)
    def score_unknown_entity(self):
        card1 = f"unseen-{random.randint(1, 10_000_000)}"
        self._score(card1)

    def _score(self, card1) -> None:
        self.client.post(
            "/score",
            json={"card1": card1, "TransactionAmt": round(random.uniform(1, 2000), 2)},
            name="/score",
        )
