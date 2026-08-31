"""Notify review_app's ingest API when a transaction is flagged.

This is a best-effort, synchronous call with a short timeout: the scoring
API's job is to return a score fast, and a review-app hiccup shouldn't take
`/score` down with it. A missed notification is a real gap (the flag never
reaches the queue), not glossed over -- worth a retry queue in a production
build; out of scope for this project's M7 (see docs/decisions.md).
"""

from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)


def notify_review_queue(
    transaction_id: str,
    card1,
    amount: float,
    score: float,
    threshold: float,
    timeout: float = 1.0,
) -> bool:
    review_app_url = os.environ.get("REVIEW_APP_URL")
    if not review_app_url:
        return False

    try:
        response = requests.post(
            f"{review_app_url.rstrip('/')}/api/flags/",
            json={
                "transaction_id": transaction_id,
                "card1": card1,
                "amount": amount,
                "score": score,
                "threshold": threshold,
            },
            headers={"X-API-Key": os.environ.get("FLAG_INGEST_API_KEY", "")},
            timeout=timeout,
        )
        return response.status_code == 201
    except requests.RequestException:
        logger.warning("failed to notify review queue for transaction %s", transaction_id, exc_info=True)
        return False
