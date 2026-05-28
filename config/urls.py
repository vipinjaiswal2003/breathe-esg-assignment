"""URL configuration for Breathe ESG API."""

from django.urls import path, re_path
from django.views.generic import TemplateView
from rest_framework.authtoken.views import obtain_auth_token

from tenants.views import (
    TenantListView, SetActiveTenantView, CurrentUserView, LoginView,
)
from ingestion.views import (
    DataSourceListView, DataSourceDetailView,
    IngestionBatchListView, IngestionBatchDetailView,
    SAPIngestionView, UtilityIngestionView, TravelIngestionView,
    EmissionFactorListView,
    NormalizedEmissionListView, NormalizedEmissionDetailView,
)
from review.views import (
    ReviewQueueView, ReviewActionView, EmissionEditView,
    ReviewCommentView, DashboardStatsView, AuditExportView,
)
from audit.views import AuditLogListView

urlpatterns = [
    # Auth
    path('api/auth/login/', LoginView.as_view(), name='api-login'),
    path('api/auth/token/', obtain_auth_token, name='api-token'),
    path('api/auth/me/', CurrentUserView.as_view(), name='current-user'),
    
    # Tenants
    path('api/tenants/', TenantListView.as_view(), name='tenant-list'),
    path('api/tenants/set-active/', SetActiveTenantView.as_view(), name='set-active-tenant'),
    
    # Data Sources
    path('api/sources/', DataSourceListView.as_view(), name='datasource-list'),
    path('api/sources/<uuid:pk>/', DataSourceDetailView.as_view(), name='datasource-detail'),
    
    # Ingestion
    path('api/ingest/batches/', IngestionBatchListView.as_view(), name='batch-list'),
    path('api/ingest/batches/<uuid:pk>/', IngestionBatchDetailView.as_view(), name='batch-detail'),
    path('api/ingest/sap/', SAPIngestionView.as_view(), name='ingest-sap'),
    path('api/ingest/utility/', UtilityIngestionView.as_view(), name='ingest-utility'),
    path('api/ingest/travel/', TravelIngestionView.as_view(), name='ingest-travel'),
    
    # Emission Factors
    path('api/emission-factors/', EmissionFactorListView.as_view(), name='emission-factor-list'),
    
    # Normalized Emissions
    path('api/emissions/', NormalizedEmissionListView.as_view(), name='emission-list'),
    path('api/emissions/<uuid:pk>/', NormalizedEmissionDetailView.as_view(), name='emission-detail'),
    
    # Review
    path('api/review/queue/', ReviewQueueView.as_view(), name='review-queue'),
    path('api/review/action/', ReviewActionView.as_view(), name='review-action'),
    path('api/review/edit/<uuid:pk>/', EmissionEditView.as_view(), name='emission-edit'),
    path('api/review/comment/<uuid:pk>/', ReviewCommentView.as_view(), name='review-comment'),
    path('api/dashboard/stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
    path('api/review/export/', AuditExportView.as_view(), name='audit-export'),
    
    # Audit
    path('api/audit/', AuditLogListView.as_view(), name='audit-log-list'),
    
    # React SPA catch-all — must be last
    re_path(r'^(?!api/|admin/|static/|media/).*$', TemplateView.as_view(template_name='index.html'), name='spa'),
]
