"""Audit views."""

from rest_framework import generics
from audit.models import AuditLog
from audit.serializers import AuditLogSerializer


class AuditLogListView(generics.ListAPIView):
    """List audit log entries for the current tenant."""
    serializer_class = AuditLogSerializer
    filterset_fields = ['action_type', 'record_type', 'performed_by']
    search_fields = ['action_detail']

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if tenant is None:
            from tenants.models import TenantMembership
            membership = TenantMembership.objects.filter(
                user=self.request.user, is_active=True, tenant__is_active=True
            ).select_related('tenant').first()
            if membership:
                tenant = membership.tenant
                self.request.tenant = tenant
        if tenant is None:
            return AuditLog.objects.none()
        return AuditLog.objects.filter(
            tenant=tenant
        ).select_related('performed_by').order_by('-timestamp')
