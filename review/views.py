"""
Review views: the analyst workflow for approving/rejecting/flagging
normalized emission records.
"""

from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone

from ingestion.models import NormalizedEmission
from review.models import ReviewAction, ReviewComment
from review.serializers import (
    ReviewActionSerializer, ReviewCommentSerializer,
    ReviewActionRequestSerializer, EmissionEditSerializer,
)
from ingestion.serializers import NormalizedEmissionListSerializer
from audit.models import AuditLog


class ReviewQueueView(generics.ListAPIView):
    """
    List emissions for review.
    
    By default shows pending records. Supports filtering by scope,
    source type, anomaly flag, status, and date range.
    """
    serializer_class = NormalizedEmissionListSerializer
    filterset_fields = ['scope', 'category', 'status', 'anomaly_flag', 'data_source', 'raw_record_type']
    search_fields = ['activity_description', 'facility_or_plant']

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
            return NormalizedEmission.objects.none()
        return NormalizedEmission.objects.filter(
            tenant=tenant
        ).select_related('data_source', 'batch').order_by('-activity_date')


class ReviewActionView(APIView):
    """
    Approve, reject, flag, lock, or unlock emission records.
    
    POST body:
    {
        "action": "approve|reject|flag|lock|unlock",
        "emission_ids": ["uuid1", "uuid2", ...],
        "notes": "optional notes"
    }
    """
    def post(self, request):
        serializer = ReviewActionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action = serializer.validated_data['action']
        emission_ids = serializer.validated_data['emission_ids']
        notes = serializer.validated_data.get('notes', '')

        tenant = request.tenant
        if not tenant:
            return Response({'error': 'No active tenant'}, status=status.HTTP_400_BAD_REQUEST)

        # Map frontend action to model status and ReviewAction action type
        action_to_status = {
            'approve': ('approved', 'approved'),
            'reject': ('rejected', 'rejected'),
            'flag': ('flagged', 'flagged'),
            'lock': ('locked', 'locked'),
            'unlock': ('pending', 'unlocked'),
        }

        action_info = action_to_status.get(action)
        if not action_info:
            return Response({'error': f'Invalid action: {action}'}, status=status.HTTP_400_BAD_REQUEST)

        new_status, review_action_type = action_info

        emissions = NormalizedEmission.objects.filter(
            id__in=emission_ids,
            tenant=tenant,
        )

        updated = []
        for emission in emissions:
            previous_status = emission.status
            
            # Prevent certain transitions
            if previous_status == 'locked' and action != 'unlock':
                continue  # Can't change a locked record without unlocking first
            
            emission.status = new_status
            if action == 'approve':
                emission.reviewed_by = request.user
                emission.reviewed_at = timezone.now()
            elif action == 'flag':
                emission.reviewed_by = request.user
                emission.reviewed_at = timezone.now()
                if notes:
                    emission.anomaly_notes = notes
            elif action == 'lock':
                emission.locked_at = timezone.now()
            elif action == 'unlock':
                emission.locked_at = None
                emission.reviewed_by = None
                emission.reviewed_at = None

            if notes:
                emission.review_notes = notes

            emission.save()

            # Create review action record — use model's ACTION_CHOICES values
            ReviewAction.objects.create(
                tenant=tenant,
                emission=emission,
                action=review_action_type,
                previous_status=previous_status,
                notes=notes,
                performed_by=request.user,
            )

            # Audit log
            AuditLog.objects.create(
                tenant=tenant,
                action_type='review',
                action_detail=f'{action} emission {emission.id}',
                record_type='NormalizedEmission',
                record_id=str(emission.id),
                performed_by=request.user,
                after_data={'status': new_status, 'notes': notes},
            )

            updated.append(str(emission.id))

        return Response({
            'action': action,
            'updated_count': len(updated),
            'updated_ids': updated,
        })


class EmissionEditView(APIView):
    """
    Edit a normalized emission record.
    
    Tracks what changed in the edit_history field and audit log.
    Only allowed when record is not locked.
    """
    def put(self, request, pk):
        tenant = request.tenant
        if not tenant:
            return Response({'error': 'No active tenant'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            emission = NormalizedEmission.objects.get(id=pk, tenant=tenant)
        except NormalizedEmission.DoesNotExist:
            return Response({'error': 'Record not found'}, status=status.HTTP_404_NOT_FOUND)

        if emission.status == 'locked':
            return Response({'error': 'Cannot edit a locked record'}, status=status.HTTP_403_FORBIDDEN)

        serializer = EmissionEditSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        changes = {}
        edit_entries = []
        for field, new_value in serializer.validated_data.items():
            old_value = getattr(emission, field)
            if old_value != new_value:
                changes[field] = {'old': old_value, 'new': new_value}
                edit_entries.append({
                    'field': field,
                    'old_value': str(old_value),
                    'new_value': str(new_value),
                    'changed_by': request.user.username,
                    'changed_at': timezone.now().isoformat(),
                })
                setattr(emission, field, new_value)

        if changes:
            # Append to edit history
            current_history = list(emission.edit_history)
            current_history.extend(edit_entries)
            emission.edit_history = current_history
            emission.is_edited = True
            emission.save()

            # Create review action
            ReviewAction.objects.create(
                tenant=tenant,
                emission=emission,
                action='edited',
                previous_status=emission.status,
                field_changes=changes,
                performed_by=request.user,
            )

            # Audit log
            AuditLog.objects.create(
                tenant=tenant,
                action_type='edit',
                action_detail=f'Edited emission {emission.id}: {list(changes.keys())}',
                record_type='NormalizedEmission',
                record_id=str(emission.id),
                performed_by=request.user,
                before_data={k: v['old'] for k, v in changes.items()},
                after_data={k: v['new'] for k, v in changes.items()},
            )

        from ingestion.serializers import NormalizedEmissionSerializer
        return Response(NormalizedEmissionSerializer(emission).data)


class ReviewCommentView(APIView):
    """Add a comment to an emission record."""
    def post(self, request, pk):
        tenant = request.tenant
        if not tenant:
            return Response({'error': 'No active tenant'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            emission = NormalizedEmission.objects.get(id=pk, tenant=tenant)
        except NormalizedEmission.DoesNotExist:
            return Response({'error': 'Record not found'}, status=status.HTTP_404_NOT_FOUND)

        comment = ReviewComment.objects.create(
            tenant=tenant,
            emission=emission,
            comment=request.data.get('comment', ''),
            author=request.user,
        )

        ReviewAction.objects.create(
            tenant=tenant,
            emission=emission,
            action='commented',
            notes=comment.comment[:200],
            performed_by=request.user,
        )

        return Response(ReviewCommentSerializer(comment).data, status=status.HTTP_201_CREATED)


class DashboardStatsView(APIView):
    """
    Dashboard statistics for the review page.
    
    Returns counts by status, scope, source type, and recent activity.
    """
    def get(self, request):
        tenant = request.tenant
        if not tenant:
            return Response({'error': 'No active tenant'}, status=status.HTTP_400_BAD_REQUEST)

        emissions = NormalizedEmission.objects.filter(tenant=tenant)

        # Status counts — use aggregation to avoid loading all records
        from django.db.models import Count, Sum
        status_agg = dict(
            emissions.values('status').annotate(count=Count('id')).values_list('status', 'count')
        )
        status_counts = {}
        for choice in NormalizedEmission.STATUS_CHOICES:
            status_counts[choice[0]] = status_agg.get(choice[0], 0)

        # Scope counts
        scope_agg = dict(
            emissions.values('scope').annotate(count=Count('id')).values_list('scope', 'count')
        )
        scope_counts = {}
        for choice in NormalizedEmission.SCOPE_CHOICES:
            scope_counts[choice[0]] = scope_agg.get(choice[0], 0)

        # Source type counts
        source_type_agg = dict(
            emissions.values('raw_record_type').annotate(count=Count('id')).values_list('raw_record_type', 'count')
        )
        source_type_counts = {
            'sap': source_type_agg.get('sap', 0),
            'utility': source_type_agg.get('utility', 0),
            'travel': source_type_agg.get('travel', 0),
        }

        # Total CO2e — use DB Sum
        total_co2e_result = emissions.aggregate(total=Sum('co2e_kg'))
        total_co2e = total_co2e_result['total'] or 0

        # Anomaly counts
        anomaly_agg = dict(
            emissions.exclude(anomaly_flag='none')
            .values('anomaly_flag').annotate(count=Count('id')).values_list('anomaly_flag', 'count')
        )
        anomaly_counts = {}
        for choice in NormalizedEmission.ANOMALY_CHOICES:
            if choice[0] != 'none':
                anomaly_counts[choice[0]] = anomaly_agg.get(choice[0], 0)

        # Total records
        total_records = emissions.count()

        # Recent batches
        from ingestion.models import IngestionBatch
        recent_batches = IngestionBatch.objects.filter(tenant=tenant).order_by('-ingested_at')[:5]

        return Response({
            'total_records': total_records,
            'total_co2e_kg': round(total_co2e, 2),
            'status_counts': status_counts,
            'scope_counts': scope_counts,
            'source_type_counts': source_type_counts,
            'anomaly_counts': anomaly_counts,
            'pending_review': status_counts.get('pending', 0),
            'flagged': status_counts.get('flagged', 0) + sum(anomaly_counts.values()),
            'recent_batches': [
                {
                    'id': str(b.id),
                    'source_name': b.data_source.name,
                    'status': b.status,
                    'total_rows': b.total_rows,
                    'successful_rows': b.successful_rows,
                    'ingested_at': b.ingested_at.isoformat(),
                }
                for b in recent_batches
            ],
        })


class AuditExportView(APIView):
    """
    Export emission data for auditors.
    
    Returns approved and locked records as structured data.
    """
    def get(self, request):
        tenant = request.tenant
        if not tenant:
            return Response({'error': 'No active tenant'}, status=status.HTTP_400_BAD_REQUEST)

        from ingestion.serializers import NormalizedEmissionSerializer

        emissions = NormalizedEmission.objects.filter(
            tenant=tenant,
            status__in=['approved', 'locked'],
        ).select_related('data_source', 'emission_factor').order_by('activity_date')

        serializer = NormalizedEmissionSerializer(emissions, many=True)

        # Audit log the export
        AuditLog.objects.create(
            tenant=tenant,
            action_type='export',
            action_detail=f'Audit export: {emissions.count()} records',
            record_type='NormalizedEmission',
            record_id='bulk',
            performed_by=request.user,
        )

        return Response({
            'export_date': timezone.now().isoformat(),
            'tenant': tenant.name,
            'total_records': emissions.count(),
            'records': serializer.data,
        })
