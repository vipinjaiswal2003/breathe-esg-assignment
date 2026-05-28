"""Serializers for the audit app."""

from rest_framework import serializers
from audit.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    performed_by_username = serializers.CharField(source='performed_by.username', read_only=True, default=None)
    action_type_display = serializers.CharField(source='get_action_type_display', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'tenant', 'action_type', 'action_type_display', 'action_detail',
            'record_type', 'record_id', 'performed_by', 'performed_by_username',
            'before_data', 'after_data', 'ip_address', 'timestamp',
        ]
        read_only_fields = ['id', 'timestamp']
