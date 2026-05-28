"""
Audit models: comprehensive audit trail for all system actions.
"""

import uuid
from django.db import models
from django.contrib.auth.models import User
from tenants.models import Tenant


class AuditLog(models.Model):
    """
    System-wide audit log. Captures every significant action:
    - Data ingestion
    - Normalization runs
    - Review actions (approve, reject, flag)
    - Edits to normalized data
    - Lock/unlock for audit
    - User authentication events
    
    Design: append-only. Records are never updated or deleted.
    This is the table that external auditors would inspect.
    """
    ACTION_TYPE_CHOICES = [
        ('ingestion', 'Data Ingestion'),
        ('normalization', 'Normalization'),
        ('review', 'Review Action'),
        ('edit', 'Data Edit'),
        ('lock', 'Lock for Audit'),
        ('unlock', 'Unlock for Correction'),
        ('export', 'Data Export'),
        ('login', 'User Login'),
        ('config_change', 'Configuration Change'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='audit_logs')
    
    action_type = models.CharField(max_length=20, choices=ACTION_TYPE_CHOICES)
    action_detail = models.CharField(max_length=255, help_text="Human-readable description")
    
    # Polymorphic reference to the affected record
    record_type = models.CharField(max_length=50, help_text="Model name: NormalizedEmission, RawSAPRecord, etc.")
    record_id = models.CharField(max_length=36, help_text="UUID of the affected record")
    
    # Who did it
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    # Before/after snapshot for edits
    before_data = models.JSONField(null=True, blank=True, help_text="State before the action")
    after_data = models.JSONField(null=True, blank=True, help_text="State after the action")
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['tenant', 'action_type']),
            models.Index(fields=['record_type', 'record_id']),
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        return f"{self.action_type}: {self.action_detail} by {self.performed_by}"
