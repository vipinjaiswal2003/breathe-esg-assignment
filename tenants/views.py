"""Tenant views."""

from rest_framework import generics, views
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login

from tenants.models import Tenant, TenantMembership
from tenants.serializers import (
    TenantSerializer, TenantMembershipSerializer,
    UserSerializer, SetActiveTenantSerializer,
)


class TenantListView(generics.ListAPIView):
    """List tenants the current user belongs to."""
    serializer_class = TenantSerializer

    def get_queryset(self):
        return Tenant.objects.filter(
            memberships__user=self.request.user,
            memberships__is_active=True,
            is_active=True,
        ).distinct().order_by('name')


class SetActiveTenantView(views.APIView):
    """Set the active tenant for the current session."""
    def post(self, request):
        serializer = SetActiveTenantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tenant_id = serializer.validated_data['tenant_id']

        # Verify membership
        try:
            membership = TenantMembership.objects.get(
                user=request.user,
                tenant_id=tenant_id,
                is_active=True,
            )
        except TenantMembership.DoesNotExist:
            return Response(
                {'error': 'You are not a member of this tenant'},
                status=status.HTTP_403_FORBIDDEN,
            )

        request.session['active_tenant_id'] = tenant_id
        return Response({'active_tenant': TenantSerializer(membership.tenant).data})


class CurrentUserView(views.APIView):
    """Get the current authenticated user with tenant info."""
    permission_classes = [IsAuthenticated]  # Only auth required, not tenant membership

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class LoginView(views.APIView):
    """Simple token-based login for the prototype."""
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response(
                {'error': 'Username and password required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        login(request, user)

        # Get or create auth token
        from rest_framework.authtoken.models import Token
        token, _ = Token.objects.get_or_create(user=user)

        return Response({
            'token': token.key,
            'user': UserSerializer(user).data,
        })
