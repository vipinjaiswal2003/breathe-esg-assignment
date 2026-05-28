"""Serializers for the ingestion app."""

from rest_framework import serializers
from ingestion.models import (
    DataSource, IngestionBatch,
    RawSAPRecord, RawUtilityRecord, RawTravelRecord,
    EmissionFactor, NormalizedEmission,
)


class DataSourceSerializer(serializers.ModelSerializer):
    source_type_display = serializers.CharField(source='get_source_type_display', read_only=True)
    ingestion_mechanism_display = serializers.CharField(source='get_ingestion_mechanism_display', read_only=True)
    record_count = serializers.SerializerMethodField()

    class Meta:
        model = DataSource
        fields = [
            'id', 'tenant', 'name', 'source_type', 'source_type_display',
            'ingestion_mechanism', 'ingestion_mechanism_display',
            'config', 'is_active', 'created_at', 'record_count',
        ]
        read_only_fields = ['id', 'created_at']

    def get_record_count(self, obj):
        return NormalizedEmission.objects.filter(data_source=obj).count()


class IngestionBatchSerializer(serializers.ModelSerializer):
    source_name = serializers.CharField(source='data_source.name', read_only=True)
    source_type = serializers.CharField(source='data_source.source_type', read_only=True)

    class Meta:
        model = IngestionBatch
        fields = [
            'id', 'tenant', 'data_source', 'source_name', 'source_type',
            'status', 'original_filename', 'total_rows', 'successful_rows',
            'failed_rows', 'flagged_rows', 'error_summary', 'quality_score',
            'ingested_at', 'ingested_by',
        ]
        read_only_fields = ['id', 'ingested_at']


class RawSAPRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawSAPRecord
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class RawUtilityRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawUtilityRecord
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class RawTravelRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawTravelRecord
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class EmissionFactorSerializer(serializers.ModelSerializer):
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = EmissionFactor
        fields = [
            'id', 'tenant', 'scope', 'scope_display', 'category', 'category_display',
            'activity_name', 'fuel_or_activity_type', 'co2e_factor', 'co2_factor',
            'ch4_factor', 'n2o_factor', 'unit', 'source', 'year', 'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class NormalizedEmissionSerializer(serializers.ModelSerializer):
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    anomaly_flag_display = serializers.CharField(source='get_anomaly_flag_display', read_only=True)
    source_name = serializers.CharField(source='data_source.name', read_only=True)
    source_type = serializers.CharField(source='data_source.source_type', read_only=True)
    batch_status = serializers.CharField(source='batch.status', read_only=True)
    emission_factor_name = serializers.CharField(source='emission_factor.activity_name', read_only=True, default=None)

    class Meta:
        model = NormalizedEmission
        fields = [
            'id', 'tenant', 'data_source', 'source_name', 'source_type',
            'batch', 'batch_status', 'emission_factor', 'emission_factor_name',
            'raw_record_type', 'raw_record_id', 'is_edited',
            'scope', 'scope_display', 'category',
            'activity_description', 'activity_quantity', 'activity_unit',
            'original_quantity', 'original_unit',
            'co2e_kg', 'co2_kg', 'ch4_kg', 'n2o_kg',
            'activity_date', 'reporting_period_start', 'reporting_period_end',
            'facility_or_plant', 'country',
            'status', 'status_display',
            'anomaly_flag', 'anomaly_flag_display', 'anomaly_notes',
            'review_notes', 'reviewed_by', 'reviewed_at', 'locked_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class NormalizedEmissionListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    anomaly_flag_display = serializers.CharField(source='get_anomaly_flag_display', read_only=True)
    source_name = serializers.CharField(source='data_source.name', read_only=True)
    source_type = serializers.CharField(source='data_source.source_type', read_only=True)

    class Meta:
        model = NormalizedEmission
        fields = [
            'id', 'scope', 'scope_display', 'category',
            'activity_description', 'activity_quantity', 'activity_unit',
            'co2e_kg', 'activity_date', 'facility_or_plant', 'country',
            'status', 'status_display',
            'anomaly_flag', 'anomaly_flag_display', 'anomaly_notes',
            'source_name', 'source_type', 'raw_record_type',
            'created_at', 'updated_at',
        ]


class IngestionUploadSerializer(serializers.Serializer):
    """Serializer for file upload endpoints."""
    file = serializers.FileField(help_text="Data file to ingest (TXT for SAP, CSV for Utility, JSON for Travel)")
    data_source_id = serializers.UUIDField(help_text="ID of the DataSource this file belongs to")
