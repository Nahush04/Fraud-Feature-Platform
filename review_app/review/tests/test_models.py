from django.db import IntegrityError, transaction
from django.test import TestCase

from review.models import Flag, Transaction


class TransactionModelTests(TestCase):
    def test_transaction_id_is_unique(self):
        Transaction.objects.create(transaction_id="txn-1", card1="1", amount="1.00", score=0.5)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Transaction.objects.create(transaction_id="txn-1", card1="2", amount="2.00", score=0.6)


class FlagModelTests(TestCase):
    def test_one_flag_per_transaction(self):
        txn = Transaction.objects.create(transaction_id="txn-1", card1="1", amount="1.00", score=0.5)
        Flag.objects.create(transaction=txn, threshold_at_flag_time=0.5)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Flag.objects.create(transaction=txn, threshold_at_flag_time=0.5)

    def test_default_status_is_pending(self):
        txn = Transaction.objects.create(transaction_id="txn-2", card1="1", amount="1.00", score=0.5)
        flag = Flag.objects.create(transaction=txn, threshold_at_flag_time=0.5)
        self.assertEqual(flag.status, Flag.Status.PENDING)
