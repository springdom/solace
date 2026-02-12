import type { Alert, AlertListResponse, AlertNote, AlertNoteListResponse, Incident, IncidentDetail, IncidentListResponse, SilenceWindow, SilenceWindowListResponse, NotificationChannel, NotificationChannelListResponse, NotificationLogListResponse } from './types';

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
    // Tags
    setTags(id: string, tags: string[]) {
      return request<Alert>(`/alerts/${id}/tags`, {
        method: 'PUT',
        body: JSON.stringify({ tags }),
      });
    },
    addTag(id: string, tag: string) {
      return request<Alert>(`/alerts/${id}/tags/${encodeURIComponent(tag)}`, { method: 'POST' });
    },
    removeTag(id: string, tag: string) {
      return request<Alert>(`/alerts/${id}/tags/${encodeURIComponent(tag)}`, { method: 'DELETE' });
    },
    // Notes
    listNotes(alertId: string) {
      return request<AlertNoteListResponse>(`/alerts/${alertId}/notes`);
    },
    addNote(alertId: string, text: string, author?: string) {
      return request<AlertNote>(`/alerts/${alertId}/notes`, {
        method: 'POST',
        body: JSON.stringify({ text, author }),
      });
    },
    updateNote(noteId: string, text: string) {
      return request<AlertNote>(`/alerts/notes/${noteId}`, {
        method: 'PUT',
        body: JSON.stringify({ text }),
      });
    },
    deleteNote(noteId: string) {
      return fetch(`${API_BASE}/alerts/notes/${noteId}`, { method: 'DELETE' });
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

  silences: {
    list(params?: { state?: string; page?: number; page_size?: number }) {
      return request<SilenceWindowListResponse>(`/silences${buildQuery(params || {})}`);
    },
    create(data: { name: string; matchers: Record<string, unknown>; starts_at: string; ends_at: string; created_by?: string; reason?: string }) {
      return request<SilenceWindow>('/silences', { method: 'POST', body: JSON.stringify(data) });
    },
    update(id: string, data: Record<string, unknown>) {
      return request<SilenceWindow>(`/silences/${id}`, { method: 'PUT', body: JSON.stringify(data) });
    },
    delete(id: string) {
      return fetch(`${API_BASE}/silences/${id}`, { method: 'DELETE' });
    },
  },

  notifications: {
    listChannels(params?: { page?: number; page_size?: number }) {
      return request<NotificationChannelListResponse>(`/notifications/channels${buildQuery(params || {})}`);
    },
    createChannel(data: { name: string; channel_type: string; config: Record<string, unknown>; filters?: Record<string, unknown> }) {
      return request<NotificationChannel>('/notifications/channels', { method: 'POST', body: JSON.stringify(data) });
    },
    updateChannel(id: string, data: Record<string, unknown>) {
      return request<NotificationChannel>(`/notifications/channels/${id}`, { method: 'PUT', body: JSON.stringify(data) });
    },
    deleteChannel(id: string) {
      return fetch(`${API_BASE}/notifications/channels/${id}`, { method: 'DELETE' });
    },
    testChannel(id: string) {
      return request<{ status: string; message: string }>(`/notifications/channels/${id}/test`, { method: 'POST' });
    },
    listLogs(params?: { channel_id?: string; incident_id?: string; page?: number; page_size?: number }) {
      return request<NotificationLogListResponse>(`/notifications/logs${buildQuery(params || {})}`);
    },
  },
};
