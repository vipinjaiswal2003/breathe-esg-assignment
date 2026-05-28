"""
Tenant model for multi-tenancy.

Design decision: Shared database, tenant-scoped via foreign key.
This is simpler than schema-per-tenant for a prototype and avoids
the operational complexity of managing multiple PostgreSQL schemas.
Every query filters by tenant_id, enforced at the model level
through a custom manager.
"""

from django.db import models
from django.contrib.auth.models import User


class Tenant(models.Model):
    """
    A client company. All data is scoped to a tenant.
    
    In production, this would include contract details, reporting periods,
    and compliance jurisdiction (determines which emission factors apply).
    """
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=100, unique=True, help_text="URL-safe identifier")
    industry = models.CharField(max_length=100, blank=True, help_text="e.g., Manufacturing, Technology")
    reporting_year_start = models.DateField(help_text="Start of the current reporting year")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'tenants'

    def __str__(self):
        return self.name


class TenantMembership(models.Model):
    """
    Links a Django User to a Tenant with a role.
    
    A user can belong to multiple tenants (e.g., a consultant
    working with multiple clients), but the UI enforces a single
    active tenant per session.
    """
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('analyst', 'Analyst'),
        ('viewer', 'Viewer'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tenant_memberships')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='analyst')
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tenant_memberships'
        unique_together = ('user', 'tenant')

    def __str__(self):
        return f"{self.user.username} → {self.tenant.name} ({self.role})"
