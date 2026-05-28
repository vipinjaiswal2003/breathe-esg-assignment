"""
Tenant-aware mixin for DRF views.

Problem: Django middleware runs before DRF's authentication.
The TenantMiddleware can't resolve request.tenant because
request.user is still AnonymousUser at middleware time.

Solution: This mixin resolves the tenant in initial() (after DRF auth)
and also applies tenant filtering to the queryset.
"""

from tenants.models import TenantMembership


class TenantAwareMixin:
    """
    Mixin for DRF views that resolves the current tenant
    after authentication has been performed.
    """
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self._resolve_tenant(request)

    def _resolve_tenant(self, request):
        """Resolve tenant after DRF authentication has set request.user."""
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
