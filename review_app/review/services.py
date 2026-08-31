"""Business logic for flagging and deciding transactions, kept out of
views.py so the same functions can be called from a script (the M7
integration point where serving/'s Flask API writes into this queue) without
going through HTTP.
"""

from __future__ import annotations

from django.db import transaction as db_transaction
from django.utils import timezone

from review.models import AuditLogEntry, Flag, Transaction


def create_flag(transaction_id: str, card1: str, amount, score: float, threshold: float) -> Flag:
    """Record a scored transaction and flag it for review. Raises
    `Transaction.MultipleObjectsReturned`-style `IntegrityError` if called
    twice for the same `transaction_id` -- a transaction is flagged once.
    """
    with db_transaction.atomic():
        txn = Transaction.objects.create(transaction_id=transaction_id, card1=card1, amount=amount, score=score)
        flag = Flag.objects.create(transaction=txn, threshold_at_flag_time=threshold)
        AuditLogEntry.objects.create(flag=flag, action=AuditLogEntry.Action.FLAGGED)
    return flag


def decide_flag(flag: Flag, approve: bool, actor, note: str = "") -> Flag:
    """Transition a PENDING flag to APPROVED or REJECTED, recording exactly
    one new audit entry -- never mutates or removes an existing one.
    """
    if flag.status != Flag.Status.PENDING:
        raise ValueError(f"flag {flag.pk} is already {flag.status}, not PENDING")

    action = AuditLogEntry.Action.APPROVED if approve else AuditLogEntry.Action.REJECTED
    status = Flag.Status.APPROVED if approve else Flag.Status.REJECTED

    with db_transaction.atomic():
        flag.status = status
        flag.decided_at = timezone.now()
        flag.decided_by = actor
        flag.save(update_fields=["status", "decided_at", "decided_by"])
        AuditLogEntry.objects.create(flag=flag, action=action, actor=actor, note=note)

    return flag
