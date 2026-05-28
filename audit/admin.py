"""Django admin for audit models."""

from django.contrib import admin
from audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action_type', 'action_detail', 'record_type', 'performed_by', 'timestamp')
    list_filter = ('action_type', 'record_type')
    readonly_fields = ('timestamp',)
    search_fields = ('action_detail', 'record_id')
