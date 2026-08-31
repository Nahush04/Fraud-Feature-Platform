from django.contrib import admin

from review.models import AuditLogEntry, Flag, Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("transaction_id", "card1", "amount", "score", "created_at")
    search_fields = ("transaction_id", "card1")


@admin.register(Flag)
class FlagAdmin(admin.ModelAdmin):
    list_display = ("transaction", "status", "created_at", "decided_at", "decided_by")
    list_filter = ("status",)


@admin.register(AuditLogEntry)
class AuditLogEntryAdmin(admin.ModelAdmin):
    list_display = ("flag", "action", "actor", "created_at")
    list_filter = ("action",)

    def has_delete_permission(self, request, obj=None):
        return False  # append-only, even from the admin
