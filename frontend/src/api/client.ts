import axios from 'axios';
import type {
  LoginRequest,
  LoginResponse,
  User,
  Tenant,
  DataSource,
  IngestionBatch,
  Emission,
  DashboardStats,
  ReviewAction,
  ReviewComment,
  AuditEntry,
  PaginatedResponse,
  EmissionFactor,
} from '../types';

const api = axios.create({
  baseURL: '/api',
});

// Request interceptor to add auth token and tenant header
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Token ${token}`;
  }
  const tenantId = localStorage.getItem('active_tenant_id');
  if (tenantId) {
    config.headers['X-Tenant-ID'] = tenantId;
  }
  return config;
});

// Response interceptor for auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('auth_user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// ---- Auth ----
export const authApi = {
  login: async (data: LoginRequest): Promise<LoginResponse> => {
    const res = await api.post('/auth/login/', data);
    return res.data;
  },
  me: async (): Promise<User> => {
    const res = await api.get('/auth/me/');
    return res.data;
  },
};

// ---- Tenants ----
export const tenantApi = {
  list: async (): Promise<Tenant[]> => {
    const res = await api.get('/tenants/');
    return res.data;
  },
  setActive: async (tenantId: number): Promise<void> => {
    await api.post('/tenants/set-active/', { tenant_id: tenantId });
    localStorage.setItem('active_tenant_id', String(tenantId));
  },
};

// ---- Data Sources ----
export const sourceApi = {
  list: async (): Promise<DataSource[]> => {
    const res = await api.get('/sources/');
    return res.data;
  },
  get: async (id: string): Promise<DataSource> => {
    const res = await api.get(`/sources/${id}/`);
    return res.data;
  },
};

// ---- Ingestion ----
export const ingestApi = {
  listBatches: async (params?: Record<string, string>): Promise<PaginatedResponse<IngestionBatch>> => {
    const res = await api.get('/ingest/batches/', { params });
    return res.data;
  },
  uploadSap: async (file: File, dataSourceId: string): Promise<IngestionBatch> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('data_source_id', dataSourceId);
    const res = await api.post('/ingest/sap/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },
  uploadUtility: async (file: File, dataSourceId: string): Promise<IngestionBatch> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('data_source_id', dataSourceId);
    const res = await api.post('/ingest/utility/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },
  uploadTravel: async (file: File, dataSourceId: string): Promise<IngestionBatch> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('data_source_id', dataSourceId);
    const res = await api.post('/ingest/travel/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },
};

// ---- Emissions ----
export const emissionApi = {
  list: async (params?: Record<string, string>): Promise<PaginatedResponse<Emission>> => {
    const res = await api.get('/emissions/', { params });
    return res.data;
  },
  get: async (id: string): Promise<Emission> => {
    const res = await api.get(`/emissions/${id}/`);
    return res.data;
  },
};

// ---- Review ----
export const reviewApi = {
  queue: async (params?: Record<string, string>): Promise<PaginatedResponse<Emission>> => {
    const res = await api.get('/review/queue/', { params });
    return res.data;
  },
  action: async (data: ReviewAction): Promise<void> => {
    await api.post('/review/action/', data);
  },
  edit: async (id: string, data: Partial<Emission>): Promise<Emission> => {
    const res = await api.put(`/review/edit/${id}/`, data);
    return res.data;
  },
  comment: async (id: string, text: string): Promise<ReviewComment> => {
    const res = await api.post(`/review/comment/${id}/`, { comment: text });
    return res.data;
  },
  export: async (): Promise<unknown> => {
    const res = await api.get('/review/export/');
    return res.data;
  },
};

// ---- Dashboard ----
export const dashboardApi = {
  stats: async (): Promise<DashboardStats> => {
    const res = await api.get('/dashboard/stats/');
    return res.data;
  },
};

// ---- Audit ----
export const auditApi = {
  list: async (params?: Record<string, string>): Promise<PaginatedResponse<AuditEntry>> => {
    const res = await api.get('/audit/', { params });
    return res.data;
  },
};

// ---- Emission Factors ----
export const factorsApi = {
  list: async (): Promise<EmissionFactor[]> => {
    const res = await api.get('/emission-factors/');
    return res.data;
  },
};

export default api;
