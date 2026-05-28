"""Serializers for the review app."""

from rest_framework import serializers
from review.models import ReviewAction, ReviewComment
from ingestion.serializers import NormalizedEmissionSerializer


class ReviewActionSerializer(serializers.ModelSerializer):
    performed_by_username = serializers.CharField(source='performed_by.username', read_only=True, default=None)

    class Meta:
        model = ReviewAction
        fields = [
            'id', 'tenant', 'emission', 'action', 'previous_status',
            'notes', 'field_changes', 'performed_by', 'performed_by_username',
            'performed_at',
        ]
        read_only_fields = ['id', 'performed_at']


class ReviewCommentSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True, default=None)

    class Meta:
        model = ReviewComment
        fields = ['id', 'emission', 'comment', 'author', 'author_username', 'created_at']
        read_only_fields = ['id', 'created_at']


class ReviewActionRequestSerializer(serializers.Serializer):
    """Serializer for review action requests."""
    action = serializers.ChoiceField(choices=['approve', 'reject', 'flag', 'lock', 'unlock'])
    emission_ids = serializers.ListField(child=serializers.UUIDField(), help_text="List of emission record IDs")
    notes = serializers.CharField(required=False, default='', allow_blank=True)


class EmissionEditSerializer(serializers.Serializer):
    """Serializer for editing normalized emission values."""
    activity_quantity = serializers.FloatField(required=False)
    activity_unit = serializers.CharField(required=False, max_length=30)
    co2e_kg = serializers.FloatField(required=False)
    category = serializers.CharField(required=False, max_length=40)
    facility_or_plant = serializers.CharField(required=False, max_length=100, allow_blank=True)
    review_notes = serializers.CharField(required=False, allow_blank=True)
