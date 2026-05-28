"""Django admin for ingestion models."""

from django.contrib import admin
from ingestion.models import (
    DataSource, IngestionBatch,
    RawSAPRecord, RawUtilityRecord, RawTravelRecord,
    EmissionFactor, NormalizedEmission,
)


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'source_type', 'ingestion_mechanism', 'tenant', 'is_active')
    list_filter = ('source_type', 'ingestion_mechanism', 'is_active')
    search_fields = ('name',)


@admin.register(IngestionBatch)
class IngestionBatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'data_source', 'status', 'total_rows', 'successful_rows', 'failed_rows', 'ingested_at')
    list_filter = ('status', 'data_source__source_type')
    readonly_fields = ('id', 'ingested_at')


@admin.register(RawSAPRecord)
class RawSAPRecordAdmin(admin.ModelAdmin):
    list_display = ('mblnr', 'bwart', 'matnr', 'werks', 'menge', 'meins', 'budat')
    list_filter = ('bwart', 'meins', 'werks')
    search_fields = ('mblnr', 'matnr', 'maktx')


@admin.register(RawUtilityRecord)
class RawUtilityRecordAdmin(admin.ModelAdmin):
    list_display = ('meter_number', 'bill_start_date', 'bill_end_date', 'consumption_kwh', 'rate_schedule')
    list_filter = ('rate_schedule', 'reading_type')
    search_fields = ('meter_number', 'account_number')


@admin.register(RawTravelRecord)
class RawTravelRecordAdmin(admin.ModelAdmin):
    list_display = ('trip_id', 'segment_type', 'origin_code', 'destination_code', 'travel_date')
    list_filter = ('segment_type', 'cabin_class')
    search_fields = ('trip_id', 'employee_id')


@admin.register(EmissionFactor)
class EmissionFactorAdmin(admin.ModelAdmin):
    list_display = ('activity_name', 'scope', 'category', 'co2e_factor', 'unit', 'source', 'year')
    list_filter = ('scope', 'category', 'year')
    search_fields = ('activity_name', 'fuel_or_activity_type')


@admin.register(NormalizedEmission)
class NormalizedEmissionAdmin(admin.ModelAdmin):
    list_display = ('id', 'scope', 'category', 'co2e_kg', 'status', 'anomaly_flag', 'activity_date')
    list_filter = ('scope', 'category', 'status', 'anomaly_flag', 'raw_record_type')
    search_fields = ('activity_description', 'facility_or_plant')
    readonly_fields = ('id', 'created_at', 'updated_at', 'edit_history')
