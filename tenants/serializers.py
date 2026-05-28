"""Serializers for the tenants app."""

from rest_framework import serializers
from django.contrib.auth.models import User
from tenants.models import Tenant, TenantMembership


class TenantSerializer(serializers.ModelSerializer):
    emission_count = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = ['id', 'name', 'slug', 'industry', 'reporting_year_start', 'is_active', 'created_at', 'emission_count', 'member_count']
        read_only_fields = ['id', 'created_at']

    def get_emission_count(self, obj):
        from ingestion.models import NormalizedEmission
        return NormalizedEmission.objects.filter(tenant=obj).count()

    def get_member_count(self, obj):
        return obj.memberships.filter(is_active=True).count()


class TenantMembershipSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)

    class Meta:
        model = TenantMembership
        fields = ['id', 'user', 'username', 'tenant', 'tenant_name', 'role', 'is_active', 'joined_at']
        read_only_fields = ['id', 'joined_at']


class UserSerializer(serializers.ModelSerializer):
    tenants = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'tenants']
        read_only_fields = ['id']

    def get_tenants(self, obj):
        memberships = TenantMembership.objects.filter(user=obj, is_active=True).select_related('tenant')
        return TenantMembershipSerializer(memberships, many=True).data


class SetActiveTenantSerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField(help_text="ID of the tenant to set as active")
