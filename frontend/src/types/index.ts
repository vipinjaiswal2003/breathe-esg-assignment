export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  tenants: TenantMembership[];
}

export interface Tenant {
  id: number;
  name: string;
  slug: string;
  industry: string;
  reporting_year_start: string;
  is_active: boolean;
  created_at: string;
  emission_count: number;
  member_count: number;
}

export interface TenantMembership {
  id: number;
  user: number;
  username: string;
  tenant: number;
  tenant_name: string;
  role: 'admin' | 'analyst' | 'viewer';
  is_active: boolean;
  joined_at: string;
}

export interface DataSource {
  id: string;
  name: string;
  source_type: 'sap' | 'utility' | 'travel';
  source_type_display: string;
  ingestion_mechanism: string;
  ingestion_mechanism_display: string;
  config: Record<string, unknown>;
  tenant: number;
  is_active: boolean;
  created_at: string;
  record_count: number;
}

export interface IngestionBatch {
  id: string;
  tenant: number;
  data_source: string;
  source_name: string;
  source_type: string;
  status: 'pending' | 'processing' | 'completed' | 'completed_with_errors' | 'failed';
  original_filename: string;
  total_rows: number;
  successful_rows: number;
  failed_rows: number;
  flagged_rows: number;
  error_summary: Record<string, unknown>;
  quality_score: number | null;
  ingested_at: string;
  ingested_by: number | null;
}

export interface Emission {
  id: string;
  tenant: number;
  data_source: string;
  source_name: string;
  source_type: string;
  batch: string;
  emission_factor: string | null;
  emission_factor_name: string | null;
  raw_record_type: string;
  raw_record_id: string;
  is_edited: boolean;
  scope: string;
  scope_display: string;
  category: string;
  activity_description: string;
  activity_quantity: number;
  activity_unit: string;
  original_quantity: number | null;
  original_unit: string;
  co2e_kg: number;
  co2_kg: number | null;
  ch4_kg: number | null;
  n2o_kg: number | null;
  activity_date: string;
  reporting_period_start: string | null;
  reporting_period_end: string | null;
  facility_or_plant: string;
  country: string;
  status: 'pending' | 'approved' | 'rejected' | 'flagged' | 'locked';
  status_display: string;
  anomaly_flag: string;
  anomaly_flag_display: string;
  anomaly_notes: string;
  review_notes: string;
  reviewed_by: number | null;
  reviewed_at: string | null;
  locked_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReviewActionRecord {
  id: string;
  tenant: number;
  emission: string;
  action: string;
  previous_status: string;
  notes: string;
  field_changes: Record<string, unknown>;
  performed_by: number | null;
  performed_by_username: string | null;
  performed_at: string;
}

export interface ReviewComment {
  id: string;
  emission: string;
  comment: string;
  author: number | null;
  author_username: string | null;
  created_at: string;
}

export interface AuditEntry {
  id: string;
  tenant: number;
  action_type: string;
  action_type_display: string;
  action_detail: string;
  record_type: string;
  record_id: string;
  performed_by: number | null;
  performed_by_username: string | null;
  before_data: Record<string, unknown> | null;
  after_data: Record<string, unknown> | null;
  ip_address: string | null;
  timestamp: string;
}

export interface DashboardStats {
  total_records: number;
  total_co2e_kg: number;
  status_counts: Record<string, number>;
  scope_counts: Record<string, number>;
  source_type_counts: Record<string, number>;
  anomaly_counts: Record<string, number>;
  pending_review: number;
  flagged: number;
  recent_batches: {
    id: string;
    source_name: string;
    status: string;
    total_rows: number;
    successful_rows: number;
    ingested_at: string;
  }[];
}

export interface ReviewAction {
  action: 'approve' | 'reject' | 'flag' | 'lock' | 'unlock';
  emission_ids: string[];
  notes?: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  token: string;
  user: User;
}

export interface EmissionFactor {
  id: string;
  tenant: number | null;
  scope: string;
  scope_display: string;
  category: string;
  category_display: string;
  activity_name: string;
  fuel_or_activity_type: string;
  co2e_factor: number;
  co2_factor: number | null;
  ch4_factor: number | null;
  n2o_factor: number | null;
  unit: string;
  source: string;
  year: number;
  is_active: boolean;
  created_at: string;
}
