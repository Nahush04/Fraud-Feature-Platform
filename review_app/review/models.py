from django.conf import settings
from django.db import models


class Transaction(models.Model):
    """A transaction the fraud-scoring API (serving/) scored, mirrored here
    for analyst review. `transaction_id` matches IEEE-CIS's `TransactionID`
    (or, in production, whatever the upstream system's transaction ID is).
    """

    transaction_id = models.CharField(max_length=64, unique=True)
    card1 = models.CharField(max_length=64)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    score = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Transaction({self.transaction_id})"


class Flag(models.Model):
    """A transaction flagged for analyst review because its score cleared
    the serving API's decision threshold. One Flag per Transaction.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE, related_name="flag")
    threshold_at_flag_time = models.FloatField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="decided_flags"
    )

    def __str__(self) -> str:
        return f"Flag({self.transaction.transaction_id}, {self.status})"


class AuditLogEntry(models.Model):
    """Append-only history for a Flag: every state change is a new row,
    never an edit to an existing one -- `delete()` is disabled below to
    enforce that at the model layer, not just by convention.
    """

    class Action(models.TextChoices):
        FLAGGED = "FLAGGED", "Flagged"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    flag = models.ForeignKey(Flag, on_delete=models.CASCADE, related_name="audit_entries")
    action = models.CharField(max_length=16, choices=Action.choices)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def delete(self, *args, **kwargs):
        raise NotImplementedError("AuditLogEntry is append-only and cannot be deleted")

    def __str__(self) -> str:
        return f"AuditLogEntry({self.flag_id}, {self.action})"
