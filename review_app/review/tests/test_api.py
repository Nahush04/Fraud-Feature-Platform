import json

from django.test import TestCase
from django.urls import reverse

from review.models import AuditLogEntry, Flag, Transaction

VALID_PAYLOAD = {
    "transaction_id": "flask-txn-1",
    "card1": "7919",
    "amount": "5000.00",
    "score": 0.91,
    "threshold": 0.75,
}


class IngestFlagApiTests(TestCase):
    def _post(self, payload, api_key="dev-local-key-change-me"):
        return self.client.post(
            reverse("ingest_flag"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_API_KEY=api_key,
        )

    def test_rejects_missing_or_wrong_api_key(self):
        resp = self._post(VALID_PAYLOAD, api_key="wrong-key")
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_creates_flag_and_audit_entry_with_valid_key(self):
        resp = self._post(VALID_PAYLOAD)

        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertIn("flag_id", body)
        self.assertEqual(body["status"], Flag.Status.PENDING)

        txn = Transaction.objects.get(transaction_id="flask-txn-1")
        self.assertEqual(str(txn.card1), "7919")
        self.assertEqual(AuditLogEntry.objects.filter(flag__transaction=txn).count(), 1)

    def test_rejects_missing_fields(self):
        resp = self._post({"transaction_id": "x"})
        self.assertEqual(resp.status_code, 400)

    def test_rejects_malformed_json(self):
        resp = self.client.post(
            reverse("ingest_flag"),
            data="not json",
            content_type="application/json",
            HTTP_X_API_KEY="dev-local-key-change-me",
        )
        self.assertEqual(resp.status_code, 400)

    def test_duplicate_transaction_id_is_a_conflict_not_a_crash(self):
        self._post(VALID_PAYLOAD)
        resp = self._post(VALID_PAYLOAD)
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(Transaction.objects.count(), 1)

    def test_get_is_not_allowed(self):
        resp = self.client.get(reverse("ingest_flag"))
        self.assertEqual(resp.status_code, 405)
