export type Severity = 'critical' | 'high' | 'warning' | 'low' | 'info';
export type AlertStatus = 'firing' | 'acknowledged' | 'resolved' | 'suppressed';
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
  starts_at: string;
  ends_at: string | null;
  last_received_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
  duplicate_count: number;
  generator_url: string | null;
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
