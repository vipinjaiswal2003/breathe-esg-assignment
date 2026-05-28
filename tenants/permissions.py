"""
Tenant permission and resolution for DRF views.

This solves the fundamental problem: Django middleware runs before
DRF's TokenAuthentication, so request.user is AnonymousUser during
TenantMiddleware.process_request().

Solution: A DRF permission class that resolves the tenant AFTER
authentication has been performed.
"""

from rest_framework.permissions import BasePermission
from tenants.models import TenantMembership


class IsTenantMember(BasePermission):
    """
    Permission class that also resolves the tenant.
    
    This runs AFTER DRF authentication, so request.user is set correctly.
    It resolves request.tenant and then checks membership.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Resolve tenant if not already set
        if not getattr(request, 'tenant', None):
            resolve_tenant(request)

        # Allow access if user has any tenant membership
        return request.tenant is not None


def resolve_tenant(request):
    """Resolve the current tenant for an authenticated request."""
    # Check X-Tenant-ID header
    tenant_id_header = request.headers.get('X-Tenant-ID')
    if tenant_id_header:
        try:
            tenant_id = int(tenant_id_header)
            membership = TenantMembership.objects.filter(
                user=request.user,
                tenant_id=tenant_id,
                is_active=True,
                tenant__is_active=True,
            ).select_related('tenant').first()
            if membership:
                request.tenant = membership.tenant
                return
        except (ValueError, TypeError):
            pass

    # Check session
    tenant_id = request.session.get('active_tenant_id')
    if tenant_id:
        from tenants.models import Tenant
        try:
            tenant = Tenant.objects.get(id=tenant_id, is_active=True)
            if TenantMembership.objects.filter(
                user=request.user, tenant=tenant, is_active=True
            ).exists():
                request.tenant = tenant
                return
        except Tenant.DoesNotExist:
            pass

    # Fallback: first active membership
    membership = TenantMembership.objects.filter(
        user=request.user,
        is_active=True,
        tenant__is_active=True,
    ).select_related('tenant').first()

    if membership:
        request.tenant = membership.tenant
    else:
        request.tenant = None
