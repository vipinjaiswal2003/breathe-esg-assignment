"""
Review models: the analyst workflow for approving/rejecting/flagging
normalized emission records before they're locked for audit.
"""

import uuid
from django.db import models
from django.contrib.auth.models import User
from tenants.models import Tenant
from ingestion.models import NormalizedEmission


class ReviewAction(models.Model):
    """
    Audit trail of every review action taken on a normalized emission.
    
    This is separate from the NormalizedEmission.status field because
    a single record may go through multiple review actions
    (e.g., flagged → approved → locked).
    """
    ACTION_CHOICES = [
        ('auto_flagged', 'Auto-Flagged by System'),
        ('flagged', 'Flagged by Analyst'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('edited', 'Values Edited'),
        ('locked', 'Locked for Audit'),
        ('unlocked', 'Unlocked for Correction'),
        ('commented', 'Comment Added'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='review_actions')
    emission = models.ForeignKey(NormalizedEmission, on_delete=models.CASCADE, related_name='review_actions')
    
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    previous_status = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    
    # For edit actions, track what changed
    field_changes = models.JSONField(default=dict, blank=True, help_text="{field: {old, new}}")
    
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    performed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'review_actions'
        ordering = ['-performed_at']

    def __str__(self):
        return f"{self.action} on {self.emission.id} by {self.performed_by}"


class ReviewComment(models.Model):
    """
    Comments on emission records during review.
    
    Separate from ReviewAction because comments don't change status
    but are part of the audit trail.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='review_comments')
    emission = models.ForeignKey(NormalizedEmission, on_delete=models.CASCADE, related_name='comments')
    
    comment = models.TextField()
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'review_comments'
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.author} on {self.emission.id}"
