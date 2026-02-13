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
