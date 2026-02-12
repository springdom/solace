import type { Alert, AlertListResponse, Incident, IncidentDetail, IncidentListResponse } from './types';

const API_BASE = '/api/v1';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function buildQuery(params: Record<string, any>): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') qs.set(k, String(v));
  }
  const s = qs.toString();
  return s ? `?${s}` : '';
}

export interface AlertListParams {
  status?: string;
  severity?: string;
  service?: string;
  q?: string;
  sort_by?: string;
  sort_order?: string;
  page?: number;
  page_size?: number;
}

export interface IncidentListParams {
  status?: string;
  q?: string;
  sort_by?: string;
  sort_order?: string;
  page?: number;
  page_size?: number;
}

export interface DashboardStats {
  alerts: {
    by_status: Record<string, number>;
    by_severity: Record<string, number>;
    total: number;
    active: number;
  };
  incidents: {
    by_status: Record<string, number>;
    total: number;
  };
  mtta_seconds: number | null;
  mttr_seconds: number | null;
}

export const api = {
  alerts: {
    list(params?: AlertListParams) {
      return request<AlertListResponse>(`/alerts${buildQuery(params || {})}`);
    },
    get(id: string) {
      return request<Alert>(`/alerts/${id}`);
    },
    acknowledge(id: string) {
      return request<Alert>(`/alerts/${id}/acknowledge`, { method: 'POST' });
    },
    resolve(id: string) {
      return request<Alert>(`/alerts/${id}/resolve`, { method: 'POST' });
    },
  },

  incidents: {
    list(params?: IncidentListParams) {
      return request<IncidentListResponse>(`/incidents${buildQuery(params || {})}`);
    },
    get(id: string) {
      return request<IncidentDetail>(`/incidents/${id}`);
    },
    acknowledge(id: string) {
      return request<Incident>(`/incidents/${id}/acknowledge`, { method: 'POST' });
    },
    resolve(id: string) {
      return request<Incident>(`/incidents/${id}/resolve`, { method: 'POST' });
    },
  },

  stats: {
    get() {
      return request<DashboardStats>('/stats');
    },
  },
};
