import { useEffect, useState } from 'react';
import type { Incident, IncidentDetail as IncidentDetailType } from '../lib/types';
import { SeverityBadge } from './SeverityBadge';
import { IncidentStatusBadge } from './IncidentStatusBadge';
import { StatusBadge } from './StatusBadge';
import { ExpandableText } from './ExpandableText';
import { formatTimestamp, duration, timeAgo } from '../lib/time';
import { api } from '../lib/api';

interface IncidentDetailProps {
  incident: Incident;
  onAcknowledge: (id: string) => void;
  onResolve: (id: string) => void;
  onClose: () => void;
}

const EVENT_ICONS: Record<string, string> = {
  incident_created: '🔔',
  alert_added: '➕',
  severity_changed: '⬆️',
  incident_acknowledged: '👁',
  incident_resolved: '✅',
  incident_auto_resolved: '🤖',
};

function AlertCard({ alert }: { alert: import('../lib/types').IncidentAlertSummary }) {
  const [expanded, setExpanded] = useState(false);
  const hasDesc = alert.description && alert.description.length > 0;

  return (
    <div
      className="px-3 py-2 rounded-md bg-solace-bg/60 border border-solace-border/50"
    >
      <div className="flex items-center gap-2">
        <SeverityBadge severity={alert.severity} />
        <div className="flex-1 min-w-0">
          <span className="text-sm font-mono text-solace-bright truncate block">
            {alert.name}
          </span>
          <span className="text-[11px] text-solace-muted font-mono">
            {[alert.service, alert.host].filter(Boolean).join(' · ') || '—'}
          </span>
        </div>
        <StatusBadge status={alert.status} />
        {alert.duplicate_count > 1 && (
          <span className="px-1.5 py-0.5 rounded bg-solace-border text-[10px] font-mono text-solace-muted">
            ×{alert.duplicate_count}
          </span>
        )}
      </div>
      {hasDesc && (
        <div className="mt-1.5 ml-7">
          {expanded ? (
            <>
              <p className="text-xs font-mono text-solace-text whitespace-pre-wrap break-words leading-relaxed">
                {alert.description}
              </p>
              <button
                onClick={() => setExpanded(false)}
                className="mt-1 text-[11px] text-blue-400 hover:text-blue-300"
              >
                ▲ Less
              </button>
            </>
          ) : (
            <button
              onClick={() => setExpanded(true)}
              className="text-[11px] text-blue-400 hover:text-blue-300"
            >
              ▼ Show error details
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export function IncidentDetail({ incident, onAcknowledge, onResolve, onClose }: IncidentDetailProps) {
  const [detail, setDetail] = useState<IncidentDetailType | null>(null);
  const isOpen = incident.status === 'open';
  const isActive = isOpen || incident.status === 'acknowledged';

  useEffect(() => {
    api.incidents.get(incident.id).then(setDetail).catch(() => {});
  }, [incident.id]);

  const events = detail?.events || [];
  const alerts = detail?.alerts || incident.alerts;

  return (
    <div className="h-full flex flex-col bg-solace-surface border-l border-solace-border animate-slide-in">
      {/* Header */}
      <div className="flex items-start justify-between p-4 border-b border-solace-border">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <SeverityBadge severity={incident.severity} pulse={isOpen} />
            <IncidentStatusBadge status={incident.status} />
          </div>
          <h2 className="font-mono text-base font-semibold text-solace-bright break-words">
            {incident.title}
          </h2>
          {incident.summary && (
            <ExpandableText text={incident.summary} maxLines={2} className="mt-1" />
          )}
        </div>
        <button
          onClick={onClose}
          className="flex-shrink-0 ml-3 p-1 rounded text-solace-muted hover:text-solace-bright hover:bg-solace-border/50 transition-colors"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 4l8 8M12 4l-8 8" />
          </svg>
        </button>
      </div>

      {/* Actions */}
      {isActive && (
        <div className="flex items-center gap-2 px-4 py-3 border-b border-solace-border">
          {isOpen && (
            <button
              onClick={() => onAcknowledge(incident.id)}
              className="flex-1 px-3 py-2 text-sm font-medium rounded-md bg-amber-500/10 text-amber-400 border border-amber-500/20 hover:bg-amber-500/20 transition-colors"
            >
              Acknowledge All
            </button>
          )}
          <button
            onClick={() => onResolve(incident.id)}
            className="flex-1 px-3 py-2 text-sm font-medium rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors"
          >
            Resolve All
          </button>
        </div>
      )}

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5">
        {/* Timing */}
        <section>
          <h3 className="text-[11px] uppercase tracking-wider text-solace-muted font-semibold mb-2">Timing</h3>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <span className="text-[10px] uppercase tracking-wider text-solace-muted block mb-0.5">Started</span>
              <span className="text-solace-bright">{formatTimestamp(incident.started_at)}</span>
            </div>
            <div>
              <span className="text-[10px] uppercase tracking-wider text-solace-muted block mb-0.5">Duration</span>
              <span className="text-solace-bright font-mono">{duration(incident.started_at, incident.resolved_at)}</span>
            </div>
          </div>
        </section>

        {/* Correlated Alerts */}
        <section>
          <h3 className="text-[11px] uppercase tracking-wider text-solace-muted font-semibold mb-2">
            Correlated Alerts ({alerts.length})
          </h3>
          <div className="space-y-1">
            {alerts.map(alert => (
              <AlertCard key={alert.id} alert={alert} />
            ))}
          </div>
        </section>

        {/* Timeline */}
        {events.length > 0 && (
          <section>
            <h3 className="text-[11px] uppercase tracking-wider text-solace-muted font-semibold mb-2">
              Timeline
            </h3>
            <div className="relative pl-5 space-y-0">
              {/* Vertical line */}
              <div className="absolute left-[7px] top-2 bottom-2 w-px bg-solace-border" />

              {events.map((event) => (
                <div key={event.id} className="relative flex items-start gap-3 py-2">
                  {/* Dot */}
                  <div className="absolute left-[-13px] top-[10px] w-2 h-2 rounded-full bg-solace-muted border-2 border-solace-surface" />

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs">{EVENT_ICONS[event.event_type] || '•'}</span>
                      <span className="text-sm text-solace-text">{event.description}</span>
                    </div>
                    <span className="text-[10px] text-solace-muted font-mono">
                      {timeAgo(event.created_at)}
                      {event.actor && event.actor !== 'system' ? ` · ${event.actor}` : ''}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Identifiers */}
        <section>
          <h3 className="text-[11px] uppercase tracking-wider text-solace-muted font-semibold mb-2">Identifiers</h3>
          <div className="text-sm">
            <span className="text-[10px] uppercase tracking-wider text-solace-muted block mb-0.5">Incident ID</span>
            <span className="text-solace-bright font-mono text-xs">{incident.id}</span>
          </div>
        </section>
      </div>
    </div>
  );
}
