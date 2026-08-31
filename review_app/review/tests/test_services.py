from django.contrib.auth.models import User
from django.test import TestCase

from review.models import AuditLogEntry, Flag, Transaction
from review.services import create_flag, decide_flag


class CreateFlagTests(TestCase):
    def test_creates_transaction_flag_and_one_audit_entry(self):
        flag = create_flag("txn-1", card1="7919", amount="125.50", score=0.9, threshold=0.75)

        self.assertEqual(Transaction.objects.count(), 1)
        self.assertEqual(Flag.objects.count(), 1)
        self.assertEqual(flag.status, Flag.Status.PENDING)

        entries = AuditLogEntry.objects.filter(flag=flag)
        self.assertEqual(entries.count(), 1)
        self.assertEqual(entries.first().action, AuditLogEntry.Action.FLAGGED)

    def test_same_transaction_id_twice_raises(self):
        create_flag("txn-1", card1="7919", amount="125.50", score=0.9, threshold=0.75)
        with self.assertRaises(Exception):
            create_flag("txn-1", card1="7919", amount="10.00", score=0.8, threshold=0.75)


class DecideFlagTests(TestCase):
    def setUp(self):
        self.analyst = User.objects.create_user("analyst1", password="x")
        self.flag = create_flag("txn-2", card1="9500", amount="500.00", score=0.95, threshold=0.75)

    def test_approve_transitions_status_and_records_one_new_audit_entry(self):
        decide_flag(self.flag, approve=True, actor=self.analyst, note="looks fine")

        self.flag.refresh_from_db()
        self.assertEqual(self.flag.status, Flag.Status.APPROVED)
        self.assertEqual(self.flag.decided_by, self.analyst)
        self.assertIsNotNone(self.flag.decided_at)

        entries = list(AuditLogEntry.objects.filter(flag=self.flag).order_by("created_at"))
        self.assertEqual(len(entries), 2)  # FLAGGED, then APPROVED -- never rewritten, only appended
        self.assertEqual(entries[0].action, AuditLogEntry.Action.FLAGGED)
        self.assertEqual(entries[1].action, AuditLogEntry.Action.APPROVED)
        self.assertEqual(entries[1].note, "looks fine")

    def test_reject_transitions_status(self):
        decide_flag(self.flag, approve=False, actor=self.analyst)
        self.flag.refresh_from_db()
        self.assertEqual(self.flag.status, Flag.Status.REJECTED)

    def test_deciding_an_already_decided_flag_raises(self):
        decide_flag(self.flag, approve=True, actor=self.analyst)
        with self.assertRaises(ValueError):
            decide_flag(self.flag, approve=False, actor=self.analyst)

    def test_deciding_twice_never_produces_a_third_audit_entry(self):
        decide_flag(self.flag, approve=True, actor=self.analyst)
        try:
            decide_flag(self.flag, approve=True, actor=self.analyst)
        except ValueError:
            pass
        self.assertEqual(AuditLogEntry.objects.filter(flag=self.flag).count(), 2)


class AuditLogEntryIsAppendOnlyTests(TestCase):
    def test_delete_is_disabled(self):
        flag = create_flag("txn-3", card1="1", amount="1.00", score=0.5, threshold=0.5)
        entry = AuditLogEntry.objects.get(flag=flag)
        with self.assertRaises(NotImplementedError):
            entry.delete()
        self.assertEqual(AuditLogEntry.objects.filter(flag=flag).count(), 1)
