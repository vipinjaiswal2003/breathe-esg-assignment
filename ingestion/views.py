"""
Ingestion views: file upload endpoints for each source type.

Each endpoint:
1. Accepts a file upload
2. Creates an IngestionBatch
3. Parses the file content
4. Creates raw records
5. Runs normalization pipeline
6. Returns batch summary with row counts and errors
"""

import json
from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from django.contrib.auth.models import User

from tenants.models import Tenant
from ingestion.models import (
    DataSource, IngestionBatch,
    RawSAPRecord, RawUtilityRecord, RawTravelRecord,
    NormalizedEmission, EmissionFactor,
)
from ingestion.serializers import (
    DataSourceSerializer, IngestionBatchSerializer,
    IngestionUploadSerializer, EmissionFactorSerializer,
    NormalizedEmissionListSerializer, NormalizedEmissionSerializer,
)
from ingestion.parsers.sap_parser import parse_sap_flat_file
from ingestion.parsers.utility_parser import parse_utility_csv
from ingestion.parsers.travel_parser import parse_travel_json
from ingestion.normalization import (
    normalize_sap_record, normalize_utility_record, normalize_travel_record,
)
from audit.models import AuditLog


class DataSourceListView(generics.ListCreateAPIView):
    """List and create data sources for the current tenant."""
    serializer_class = DataSourceSerializer

    def get_queryset(self):
        return DataSource.objects.filter(tenant=self.request.tenant).order_by('name')


class DataSourceDetailView(generics.RetrieveAPIView):
    """Get details of a single data source."""
    serializer_class = DataSourceSerializer

    def get_queryset(self):
        return DataSource.objects.filter(tenant=self.request.tenant)


class IngestionBatchListView(generics.ListAPIView):
    """List ingestion batches for the current tenant."""
    serializer_class = IngestionBatchSerializer

    def get_queryset(self):
        return IngestionBatch.objects.filter(tenant=self.request.tenant).select_related('data_source')


class IngestionBatchDetailView(generics.RetrieveAPIView):
    """Get details of a single ingestion batch."""
    serializer_class = IngestionBatchSerializer

    def get_queryset(self):
        return IngestionBatch.objects.filter(tenant=self.request.tenant).select_related('data_source')


class SAPIngestionView(APIView):
    """
    Upload and ingest SAP flat-file data.
    
    Accepts: tab-delimited text file (SAP SE16N export format)
    Returns: batch summary with row counts and parsing errors
    """
    parser_classes = [MultiPartParser]

    def post(self, request):
        tenant = request.tenant
        if not tenant:
            return Response({'error': 'No active tenant'}, status=status.HTTP_400_BAD_REQUEST)

        file = request.FILES.get('file')
        data_source_id = request.data.get('data_source_id')

        if not file:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

        # Get or create data source
        try:
            data_source = DataSource.objects.get(id=data_source_id, tenant=tenant, source_type='sap')
        except DataSource.DoesNotExist:
            return Response({'error': 'SAP data source not found'}, status=status.HTTP_404_NOT_FOUND)

        # Read file content
        content = file.read().decode('utf-8', errors='replace')

        # Create batch
        batch = IngestionBatch.objects.create(
            tenant=tenant,
            data_source=data_source,
            status='processing',
            original_filename=file.name,
            file_content=content[:500000],  # Store first 500KB for audit
            ingested_by=request.user,
        )

        # Parse
        parsed_records, parse_errors = parse_sap_flat_file(content, data_source.config)

        # Create raw records and normalize
        successful = 0
        failed = 0
        flagged = 0

        for parsed in parsed_records:
            try:
                raw = RawSAPRecord.objects.create(
                    tenant=tenant,
                    batch=batch,
                    data_source=data_source,
                    mblnr=parsed.get('mblnr', ''),
                    mjahr=parsed.get('mjahr', ''),
                    zeile=parsed.get('zeile', ''),
                    bwart=parsed.get('bwart', ''),
                    matnr=parsed.get('matnr', ''),
                    maktx=parsed.get('maktx', ''),
                    matkl=parsed.get('matkl', ''),
                    werks=parsed.get('werks', ''),
                    menge=parsed.get('menge', ''),
                    meins=parsed.get('meins', ''),
                    budat=parsed.get('budat', ''),
                    kostl=parsed.get('kostl', ''),
                    anln1=parsed.get('anln1', ''),
                    aufnr=parsed.get('aufnr', ''),
                    lgort=parsed.get('lgort', ''),
                    lifnr=parsed.get('lifnr', ''),
                    ebelp=parsed.get('ebelp', ''),
                    parse_errors=parsed.get('_parse_errors', []),
                    is_parsed=True,
                )

                # Normalize
                normalized = normalize_sap_record(raw, tenant)
                if normalized:
                    normalized.save()
                    successful += 1
                    if normalized.anomaly_flag != 'none':
                        flagged += 1
                else:
                    successful += 1  # Parsed OK but not a fuel record (e.g., BWART 101)

            except Exception as e:
                failed += 1
                parse_errors.append({
                    'row_number': 0,
                    'field': 'database',
                    'message': str(e),
                    'raw_value': '',
                })

        # Update batch
        batch.total_rows = len(parsed_records)
        batch.successful_rows = successful
        batch.failed_rows = failed
        batch.flagged_rows = flagged
        batch.status = 'completed_with_errors' if (failed > 0 or len(parse_errors) > 0) else 'completed'
        batch.error_summary = {
            'total_parse_errors': len(parse_errors),
            'sample_errors': parse_errors[:10],
        }
        batch.quality_score = round((successful / max(len(parsed_records), 1)) * 100, 1)
        batch.save()

        # Audit log
        AuditLog.objects.create(
            tenant=tenant,
            action_type='ingestion',
            action_detail=f'SAP ingestion: {file.name} — {successful} records',
            record_type='IngestionBatch',
            record_id=str(batch.id),
            performed_by=request.user,
        )

        return Response(IngestionBatchSerializer(batch).data, status=status.HTTP_201_CREATED)


class UtilityIngestionView(APIView):
    """
    Upload and ingest utility CSV data.
    
    Accepts: CSV file (utility portal export format)
    Returns: batch summary with row counts and parsing errors
    """
    parser_classes = [MultiPartParser]

    def post(self, request):
        tenant = request.tenant
        if not tenant:
            return Response({'error': 'No active tenant'}, status=status.HTTP_400_BAD_REQUEST)

        file = request.FILES.get('file')
        data_source_id = request.data.get('data_source_id')

        if not file:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            data_source = DataSource.objects.get(id=data_source_id, tenant=tenant, source_type='utility')
        except DataSource.DoesNotExist:
            return Response({'error': 'Utility data source not found'}, status=status.HTTP_404_NOT_FOUND)

        content = file.read().decode('utf-8', errors='replace')

        batch = IngestionBatch.objects.create(
            tenant=tenant,
            data_source=data_source,
            status='processing',
            original_filename=file.name,
            file_content=content[:500000],
            ingested_by=request.user,
        )

        parsed_records, parse_errors = parse_utility_csv(content, data_source.config)

        successful = 0
        failed = 0
        flagged = 0

        for parsed in parsed_records:
            try:
                raw = RawUtilityRecord.objects.create(
                    tenant=tenant,
                    batch=batch,
                    data_source=data_source,
                    account_number=parsed.get('account_number', ''),
                    meter_number=parsed.get('meter_number', ''),
                    service_address=parsed.get('service_address', ''),
                    rate_schedule=parsed.get('rate_schedule', ''),
                    bill_start_date=parsed.get('bill_start_date', ''),
                    bill_end_date=parsed.get('bill_end_date', ''),
                    bill_days=parsed.get('_parsed_bill_days'),
                    consumption_kwh=parsed.get('consumption_kwh', ''),
                    demand_kw=parsed.get('demand_kw', ''),
                    meter_multiplier=parsed.get('_parsed_multiplier', 1.0),
                    reading_type=parsed.get('reading_type', ''),
                    total_charge=parsed.get('total_charge', ''),
                    parse_errors=parsed.get('_parse_errors', []),
                    is_parsed=True,
                )

                normalized = normalize_utility_record(raw, tenant)
                if normalized:
                    normalized.save()
                    successful += 1
                    if normalized.anomaly_flag != 'none':
                        flagged += 1
                else:
                    failed += 1

            except Exception as e:
                failed += 1
                parse_errors.append({
                    'row_number': 0,
                    'field': 'database',
                    'message': str(e),
                    'raw_value': '',
                })

        batch.total_rows = len(parsed_records)
        batch.successful_rows = successful
        batch.failed_rows = failed
        batch.flagged_rows = flagged
        batch.status = 'completed_with_errors' if (failed > 0 or len(parse_errors) > 0) else 'completed'
        batch.error_summary = {
            'total_parse_errors': len(parse_errors),
            'sample_errors': parse_errors[:10],
        }
        batch.quality_score = round((successful / max(len(parsed_records), 1)) * 100, 1)
        batch.save()

        AuditLog.objects.create(
            tenant=tenant,
            action_type='ingestion',
            action_detail=f'Utility ingestion: {file.name} — {successful} records',
            record_type='IngestionBatch',
            record_id=str(batch.id),
            performed_by=request.user,
        )

        return Response(IngestionBatchSerializer(batch).data, status=status.HTTP_201_CREATED)


class TravelIngestionView(APIView):
    """
    Upload and ingest corporate travel JSON data.
    
    Accepts: JSON file (Concur Itinerary API format)
    Returns: batch summary with row counts and parsing errors
    """
    parser_classes = [MultiPartParser]

    def post(self, request):
        tenant = request.tenant
        if not tenant:
            return Response({'error': 'No active tenant'}, status=status.HTTP_400_BAD_REQUEST)

        file = request.FILES.get('file')
        data_source_id = request.data.get('data_source_id')

        if not file:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            data_source = DataSource.objects.get(id=data_source_id, tenant=tenant, source_type='travel')
        except DataSource.DoesNotExist:
            return Response({'error': 'Travel data source not found'}, status=status.HTTP_404_NOT_FOUND)

        content = file.read().decode('utf-8', errors='replace')

        batch = IngestionBatch.objects.create(
            tenant=tenant,
            data_source=data_source,
            status='processing',
            original_filename=file.name,
            file_content=content[:500000],
            ingested_by=request.user,
        )

        parsed_records, parse_errors = parse_travel_json(content, data_source.config)

        successful = 0
        failed = 0
        flagged = 0

        for parsed in parsed_records:
            try:
                raw = RawTravelRecord.objects.create(
                    tenant=tenant,
                    batch=batch,
                    data_source=data_source,
                    trip_id=parsed.get('trip_id', ''),
                    segment_type=parsed.get('segment_type', ''),
                    employee_id=parsed.get('employee_id', ''),
                    origin_code=parsed.get('origin_code', ''),
                    destination_code=parsed.get('destination_code', ''),
                    cabin_class=parsed.get('cabin_class', ''),
                    airline_code=parsed.get('airline_code', ''),
                    hotel_city=parsed.get('hotel_city', ''),
                    hotel_country=parsed.get('hotel_country', ''),
                    nights=parsed.get('nights'),
                    car_type=parsed.get('car_type', ''),
                    car_fuel_type=parsed.get('car_fuel_type', ''),
                    distance_km=parsed.get('distance_km', ''),
                    travel_date=parsed.get('travel_date', ''),
                    distance_miles=parsed.get('distance_miles', ''),
                    raw_segment_data=parsed.get('raw_segment_data', {}),
                    parse_errors=parsed.get('_parse_errors', []),
                    is_parsed=True,
                )

                normalized = normalize_travel_record(raw, tenant)
                if normalized:
                    normalized.save()
                    successful += 1
                    if normalized.anomaly_flag != 'none':
                        flagged += 1
                else:
                    failed += 1

            except Exception as e:
                failed += 1
                parse_errors.append({
                    'row_number': 0,
                    'field': 'database',
                    'message': str(e),
                    'raw_value': '',
                })

        batch.total_rows = len(parsed_records)
        batch.successful_rows = successful
        batch.failed_rows = failed
        batch.flagged_rows = flagged
        batch.status = 'completed_with_errors' if (failed > 0 or len(parse_errors) > 0) else 'completed'
        batch.error_summary = {
            'total_parse_errors': len(parse_errors),
            'sample_errors': parse_errors[:10],
        }
        batch.quality_score = round((successful / max(len(parsed_records), 1)) * 100, 1)
        batch.save()

        AuditLog.objects.create(
            tenant=tenant,
            action_type='ingestion',
            action_detail=f'Travel ingestion: {file.name} — {successful} records',
            record_type='IngestionBatch',
            record_id=str(batch.id),
            performed_by=request.user,
        )

        return Response(IngestionBatchSerializer(batch).data, status=status.HTTP_201_CREATED)


class EmissionFactorListView(generics.ListAPIView):
    """List emission factors for the current tenant."""
    serializer_class = EmissionFactorSerializer
    filterset_fields = ['scope', 'category', 'fuel_or_activity_type', 'is_active']

    def get_queryset(self):
        from django.db.models import Q
        return EmissionFactor.objects.filter(
            Q(tenant=self.request.tenant) | Q(tenant__isnull=True),
            is_active=True,
        ).order_by('scope', 'category')


class NormalizedEmissionListView(generics.ListAPIView):
    """List normalized emissions with filtering."""
    serializer_class = NormalizedEmissionListSerializer
    filterset_fields = ['scope', 'category', 'status', 'anomaly_flag', 'data_source', 'raw_record_type']
    search_fields = ['activity_description', 'facility_or_plant']

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if tenant is None:
            # Fallback: get user's first tenant
            from tenants.models import TenantMembership
            membership = TenantMembership.objects.filter(
                user=self.request.user, is_active=True, tenant__is_active=True
            ).select_related('tenant').first()
            if membership:
                tenant = membership.tenant
                self.request.tenant = tenant
        if tenant is None:
            return NormalizedEmission.objects.none()
        return NormalizedEmission.objects.filter(
            tenant=tenant
        ).select_related('data_source', 'batch')


class NormalizedEmissionDetailView(generics.RetrieveAPIView):
    """Get full details of a single normalized emission record."""
    serializer_class = NormalizedEmissionSerializer

    def get_queryset(self):
        return NormalizedEmission.objects.filter(
            tenant=self.request.tenant
        ).select_related('data_source', 'batch', 'emission_factor')
