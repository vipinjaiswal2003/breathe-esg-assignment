"""
Tenant middleware: sets request.tenant based on user's membership.

This is a simple approach for a prototype: the active tenant is stored
in the user's session. In production, you'd want a tenant selector
in the UI that persists the choice.

Design tradeoff: I chose session-based tenant selection over subdomain-based
(e.g., client1.breatheesg.com) because it's simpler to deploy and doesn't
require DNS configuration or wildcard SSL certificates.
"""

from django.utils.deprecation import MiddlewareMixin
from tenants.models import Tenant, TenantMembership


class TenantMiddleware(MiddlewareMixin):
    """
    Adds request.tenant to every request.
    
    Resolution order:
    1. X-Tenant-ID header (for API clients)
    2. Session-stored tenant ID
    3. User's first active membership (fallback)
    4. None (anonymous user)
    """
    def process_request(self, request):
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            request.tenant = None
            return

        # Check X-Tenant-ID header first (for token-based API auth)
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
            try:
                request.tenant = Tenant.objects.get(id=tenant_id, is_active=True)
                # Verify user is a member
                if TenantMembership.objects.filter(
                    user=request.user, tenant=request.tenant, is_active=True
                ).exists():
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
            try:
                request.session['active_tenant_id'] = membership.tenant.id
            except Exception:
                pass  # Session may not be available with token auth
        else:
            request.tenant = None
