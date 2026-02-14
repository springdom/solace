export type Severity = 'critical' | 'high' | 'warning' | 'low' | 'info';
export type AlertStatus = 'firing' | 'acknowledged' | 'resolved' | 'suppressed' | 'archived';
export type IncidentStatus = 'open' | 'acknowledged' | 'resolved';

export interface Alert {
  id: string;
  fingerprint: string;
  source: string;
  source_instance: string | null;
  status: AlertStatus;
  severity: Severity;
  name: string;
  description: string | null;
  service: string | null;
  environment: string | null;
  host: string | null;
  labels: Record<string, string>;
  annotations: Record<string, string>;
  tags: string[];
  raw_payload: Record<string, unknown> | null;
  starts_at: string;
  ends_at: string | null;
  last_received_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
  duplicate_count: number;
  generator_url: string | null;
  runbook_url: string | null;
  ticket_url: string | null;
  archived_at: string | null;
  incident_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface AlertListResponse {
  alerts: Alert[];
  total: number;
  page: number;
  page_size: number;
}

export interface AlertNote {
  id: string;
  alert_id: string;
  text: string;
  author: string | null;
  created_at: string;
  updated_at: string;
}

export interface AlertNoteListResponse {
  notes: AlertNote[];
  total: number;
}

export interface IncidentAlertSummary {
  id: string;
  name: string;
  status: AlertStatus;
  severity: Severity;
  description: string | null;
  service: string | null;
  host: string | null;
  duplicate_count: number;
  starts_at: string;
}

export interface Incident {
  id: string;
  title: string;
  status: IncidentStatus;
  severity: Severity;
  summary: string | null;
  phase: string | null;
  started_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
  alert_count: number;
  alerts: IncidentAlertSummary[];
  created_at: string;
  updated_at: string;
}

export interface IncidentEvent {
  id: string;
  event_type: string;
  description: string;
  actor: string | null;
  event_data: Record<string, unknown>;
  created_at: string;
}

export interface IncidentDetail extends Incident {
  events: IncidentEvent[];
}

export interface IncidentListResponse {
  incidents: Incident[];
  total: number;
  page: number;
  page_size: number;
}

export interface SilenceWindow {
  id: string;
  name: string;
  matchers: {
    service?: string[];
    severity?: string[];
    labels?: Record<string, string>;
  };
  starts_at: string;
  ends_at: string;
  created_by: string | null;
  reason: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SilenceWindowListResponse {
  windows: SilenceWindow[];
  total: number;
  page: number;
  page_size: number;
}

export type ChannelType = 'slack' | 'email' | 'teams' | 'webhook' | 'pagerduty';
export type NotificationStatus = 'pending' | 'sent' | 'failed';

export interface NotificationChannel {
  id: string;
  name: string;
  channel_type: ChannelType;
  config: Record<string, unknown>;
  is_active: boolean;
  filters: {
    severity?: string[];
    service?: string[];
  };
  created_at: string;
  updated_at: string;
}

export interface NotificationChannelListResponse {
  channels: NotificationChannel[];
  total: number;
  page: number;
  page_size: number;
}

export interface NotificationLog {
  id: string;
  channel_id: string;
  incident_id: string;
  event_type: string;
  status: NotificationStatus;
  error_message: string | null;
  sent_at: string | null;
  created_at: string;
}

export interface NotificationLogListResponse {
  logs: NotificationLog[];
  total: number;
  page: number;
  page_size: number;
}

export interface AlertOccurrence {
  id: string;
  alert_id: string;
  received_at: string;
}

export interface AlertOccurrenceListResponse {
  occurrences: AlertOccurrence[];
  total: number;
}

export interface AppSettings {
  app_name: string;
  app_env: string;
  dedup_window_seconds: number;
  correlation_window_seconds: number;
  notification_cooldown_seconds: number;
  solace_dashboard_url: string;
}

// ─── Auth ─────────────────────────────────────────────────

export type UserRole = 'admin' | 'user' | 'viewer';

export interface UserProfile {
  id: string;
  email: string;
  username: string;
  display_name: string;
  role: UserRole;
  is_active: boolean;
  must_change_password: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserProfile;
  must_change_password: boolean;
}

export interface UserListResponse {
  users: UserProfile[];
  total: number;
}

// ─── On-Call ──────────────────────────────────────────────

export interface OnCallOverride {
  id: string;
  schedule_id: string;
  user_id: string;
  starts_at: string;
  ends_at: string;
  reason: string | null;
  created_at: string;
}

export interface OnCallSchedule {
  id: string;
  name: string;
  description: string | null;
  timezone: string;
  rotation_type: 'hourly' | 'daily' | 'weekly' | 'custom';
  members: Array<{ user_id: string; order: number }>;
  handoff_time: string;
  rotation_interval_days: number;
  rotation_interval_hours: number | null;
  effective_from: string;
  is_active: boolean;
  overrides: OnCallOverride[];
  created_at: string;
  updated_at: string;
}

export interface OnCallScheduleListResponse {
  schedules: OnCallSchedule[];
  total: number;
}

export interface OnCallCurrentResponse {
  schedule_id: string;
  schedule_name: string;
  user: UserProfile | null;
}

export interface EscalationPolicy {
  id: string;
  name: string;
  description: string | null;
  repeat_count: number;
  levels: Array<{
    level: number;
    targets: Array<{ type: 'user' | 'schedule'; id: string }>;
    timeout_minutes: number;
  }>;
  created_at: string;
  updated_at: string;
}

export interface EscalationPolicyListResponse {
  policies: EscalationPolicy[];
  total: number;
}

export interface ServiceMapping {
  id: string;
  service_pattern: string;
  severity_filter: string[] | null;
  escalation_policy_id: string;
  priority: number;
  created_at: string | null;
}
