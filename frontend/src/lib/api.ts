import type {
  Alert, AlertListResponse, AlertNote, AlertNoteListResponse,
  AlertOccurrenceListResponse, AppSettings, EscalationPolicy,
  EscalationPolicyListResponse, Incident, IncidentDetail,
  IncidentListResponse, LoginResponse, NotificationChannel,
  NotificationChannelListResponse, NotificationLogListResponse,
  OnCallCurrentResponse, OnCallOverride, OnCallSchedule,
  OnCallScheduleListResponse, ServiceMapping, SilenceWindow,
  SilenceWindowListResponse, UserListResponse, UserProfile,
} from './types';

const API_BASE = '/api/v1';
const TOKEN_KEY = 'solace_token';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

let _redirecting = false;

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  const token = getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    headers,
    ...options,
  });

  if (res.status === 401) {
    if (!_redirecting) {
      _redirecting = true;
      clearToken();
      window.location.reload();
    }
    throw new Error('Unauthorized');
  }

  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

// Raw fetch with auth for DELETE (no JSON body response)
async function authFetch(path: string, options?: RequestInit): Promise<Response> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}${path}`, { headers, ...options });
  if (res.status === 401 && !_redirecting) {
    _redirecting = true;
    clearToken();
    window.location.reload();
  }
  return res;
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
  tag?: string;
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
  auth: {
    login(username: string, password: string) {
      return request<LoginResponse>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      });
    },
    me() {
      return request<UserProfile>('/auth/me');
    },
    changePassword(currentPassword: string, newPassword: string) {
      return request<{ message: string }>('/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
    },
  },

  users: {
    list(params?: { page?: number; page_size?: number }) {
      return request<UserListResponse>(`/users${buildQuery(params || {})}`);
    },
    create(data: { email: string; username: string; password: string; role?: string }) {
      return request<UserProfile>('/users', { method: 'POST', body: JSON.stringify(data) });
    },
    update(id: string, data: Record<string, unknown>) {
      return request<UserProfile>(`/users/${id}`, { method: 'PUT', body: JSON.stringify(data) });
    },
    resetPassword(id: string, newPassword: string) {
      return request<UserProfile>(`/users/${id}/reset-password`, {
        method: 'POST',
        body: JSON.stringify({ new_password: newPassword }),
      });
    },
    delete(id: string) {
      return authFetch(`/users/${id}`, { method: 'DELETE' });
    },
  },

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
      return authFetch(`/alerts/notes/${noteId}`, { method: 'DELETE' });
    },
    getHistory(alertId: string) {
      return request<AlertOccurrenceListResponse>(`/alerts/${alertId}/history`);
    },
    setTicketUrl(alertId: string, ticketUrl: string) {
      return request<Alert>(`/alerts/${alertId}/ticket`, {
        method: 'PUT',
        body: JSON.stringify({ ticket_url: ticketUrl }),
      });
    },
    bulkAcknowledge(alertIds: string[]) {
      return request<{ updated: number; alert_ids: string[] }>('/alerts/bulk/acknowledge', {
        method: 'POST',
        body: JSON.stringify({ alert_ids: alertIds }),
      });
    },
    bulkResolve(alertIds: string[]) {
      return request<{ updated: number; alert_ids: string[] }>('/alerts/bulk/resolve', {
        method: 'POST',
        body: JSON.stringify({ alert_ids: alertIds }),
      });
    },
    archive(olderThanDays?: number) {
      const params = olderThanDays ? { older_than_days: olderThanDays } : {};
      return request<{ archived: number }>(`/alerts/archive${buildQuery(params)}`, { method: 'POST' });
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
      return authFetch(`/silences/${id}`, { method: 'DELETE' });
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
      return authFetch(`/notifications/channels/${id}`, { method: 'DELETE' });
    },
    testChannel(id: string) {
      return request<{ status: string; message: string }>(`/notifications/channels/${id}/test`, { method: 'POST' });
    },
    listLogs(params?: { channel_id?: string; incident_id?: string; page?: number; page_size?: number }) {
      return request<NotificationLogListResponse>(`/notifications/logs${buildQuery(params || {})}`);
    },
  },

  settings: {
    get() {
      return request<AppSettings>('/settings');
    },
  },

  oncall: {
    listSchedules(params?: { active_only?: boolean; page?: number; page_size?: number }) {
      return request<OnCallScheduleListResponse>(`/oncall/schedules${buildQuery(params || {})}`);
    },
    getSchedule(id: string) {
      return request<OnCallSchedule>(`/oncall/schedules/${id}`);
    },
    createSchedule(data: Record<string, unknown>) {
      return request<OnCallSchedule>('/oncall/schedules', { method: 'POST', body: JSON.stringify(data) });
    },
    updateSchedule(id: string, data: Record<string, unknown>) {
      return request<OnCallSchedule>(`/oncall/schedules/${id}`, { method: 'PUT', body: JSON.stringify(data) });
    },
    deleteSchedule(id: string) {
      return authFetch(`/oncall/schedules/${id}`, { method: 'DELETE' });
    },
    getCurrentOnCall(scheduleId: string) {
      return request<OnCallCurrentResponse>(`/oncall/schedules/${scheduleId}/current`);
    },
    createOverride(scheduleId: string, data: { user_id: string; starts_at: string; ends_at: string; reason?: string }) {
      return request<OnCallOverride>(`/oncall/schedules/${scheduleId}/overrides`, { method: 'POST', body: JSON.stringify(data) });
    },
    deleteOverride(overrideId: string) {
      return authFetch(`/oncall/overrides/${overrideId}`, { method: 'DELETE' });
    },
    listPolicies(params?: { page?: number; page_size?: number }) {
      return request<EscalationPolicyListResponse>(`/oncall/policies${buildQuery(params || {})}`);
    },
    getPolicy(id: string) {
      return request<EscalationPolicy>(`/oncall/policies/${id}`);
    },
    createPolicy(data: Record<string, unknown>) {
      return request<EscalationPolicy>('/oncall/policies', { method: 'POST', body: JSON.stringify(data) });
    },
    updatePolicy(id: string, data: Record<string, unknown>) {
      return request<EscalationPolicy>(`/oncall/policies/${id}`, { method: 'PUT', body: JSON.stringify(data) });
    },
    deletePolicy(id: string) {
      return authFetch(`/oncall/policies/${id}`, { method: 'DELETE' });
    },
    listMappings() {
      return request<ServiceMapping[]>('/oncall/mappings');
    },
    createMapping(data: { service_pattern: string; severity_filter?: string[]; escalation_policy_id: string; priority?: number }) {
      return request<ServiceMapping>('/oncall/mappings', { method: 'POST', body: JSON.stringify(data) });
    },
    deleteMapping(id: string) {
      return authFetch(`/oncall/mappings/${id}`, { method: 'DELETE' });
    },
  },
};
