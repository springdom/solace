import type { Alert } from '../lib/types';
import { SeverityBadge } from './SeverityBadge';
import { StatusBadge } from './StatusBadge';
import { ExpandableText } from './ExpandableText';
import { formatTimestamp, duration } from '../lib/time';

interface AlertDetailProps {
  alert: Alert;
  onAcknowledge: (id: string) => void;
  onResolve: (id: string) => void;
  onClose: () => void;
}

function Field({ label, value, mono }: { label: string; value: string | null | undefined; mono?: boolean }) {
  if (!value) return null;
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-wider text-solace-muted font-medium mb-0.5">{label}</dt>
      <dd className={`text-sm text-solace-bright ${mono ? 'font-mono' : ''}`}>{value}</dd>
    </div>
  );
}

export function AlertDetail({ alert, onAcknowledge, onResolve, onClose }: AlertDetailProps) {
  const isFiring = alert.status === 'firing';
  const isActive = isFiring || alert.status === 'acknowledged';

  return (
    <div className="h-full flex flex-col bg-solace-surface border-l border-solace-border animate-slide-in">
      {/* Header */}
      <div className="flex items-start justify-between p-4 border-b border-solace-border">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <SeverityBadge severity={alert.severity} pulse={isFiring} />
            <StatusBadge status={alert.status} />
          </div>
          <h2 className="font-mono text-base font-semibold text-solace-bright break-words">
            {alert.name}
          </h2>
          {alert.description && (
            <ExpandableText text={alert.description} maxLines={2} className="mt-1" />
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
          {isFiring && (
            <button
              onClick={() => onAcknowledge(alert.id)}
              className="flex-1 px-3 py-2 text-sm font-medium rounded-md bg-amber-500/10 text-amber-400 border border-amber-500/20 hover:bg-amber-500/20 transition-colors"
            >
              Acknowledge
            </button>
          )}
          <button
            onClick={() => onResolve(alert.id)}
            className="flex-1 px-3 py-2 text-sm font-medium rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors"
          >
            Resolve
          </button>
        </div>
      )}

      {/* Details */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Timing */}
        <section>
          <h3 className="text-[11px] uppercase tracking-wider text-solace-muted font-semibold mb-2">Timing</h3>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Started" value={formatTimestamp(alert.starts_at)} />
            <Field label="Duration" value={duration(alert.starts_at, alert.ends_at)} mono />
            {alert.acknowledged_at && (
              <Field label="Acknowledged" value={formatTimestamp(alert.acknowledged_at)} />
            )}
            {alert.resolved_at && (
              <Field label="Resolved" value={formatTimestamp(alert.resolved_at)} />
            )}
          </div>
        </section>

        {/* Source */}
        <section>
          <h3 className="text-[11px] uppercase tracking-wider text-solace-muted font-semibold mb-2">Source</h3>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Source" value={alert.source} mono />
            <Field label="Service" value={alert.service} mono />
            <Field label="Host" value={alert.host} mono />
            <Field label="Environment" value={alert.environment} mono />
          </div>
        </section>

        {/* Identifiers */}
        <section>
          <h3 className="text-[11px] uppercase tracking-wider text-solace-muted font-semibold mb-2">Identifiers</h3>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Fingerprint" value={alert.fingerprint} mono />
            <Field label="Duplicates" value={String(alert.duplicate_count)} mono />
            <Field label="ID" value={alert.id.slice(0, 8) + '...'} mono />
          </div>
        </section>

        {/* Labels */}
        {Object.keys(alert.labels).length > 0 && (
          <section>
            <h3 className="text-[11px] uppercase tracking-wider text-solace-muted font-semibold mb-2">Labels</h3>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(alert.labels).map(([key, value]) => (
                <span
                  key={key}
                  className="inline-flex items-center px-2 py-0.5 rounded bg-solace-border/50 text-xs font-mono"
                >
                  <span className="text-solace-muted">{key}=</span>
                  <span className="text-solace-bright">{value}</span>
                </span>
              ))}
            </div>
          </section>
        )}

        {/* Annotations */}
        {Object.keys(alert.annotations).length > 0 && (
          <section>
            <h3 className="text-[11px] uppercase tracking-wider text-solace-muted font-semibold mb-2">Annotations</h3>
            <div className="space-y-2">
              {Object.entries(alert.annotations).map(([key, value]) => (
                <div key={key}>
                  <dt className="text-[10px] uppercase tracking-wider text-solace-muted">{key}</dt>
                  <dd className="text-sm text-solace-text mt-0.5">
                    {key.includes('url') ? (
                      <a href={value} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline">
                        {value}
                      </a>
                    ) : value}
                  </dd>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Generator URL */}
        {alert.generator_url && (
          <section>
            <h3 className="text-[11px] uppercase tracking-wider text-solace-muted font-semibold mb-2">Links</h3>
            <a
              href={alert.generator_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-sm text-blue-400 hover:underline"
            >
              <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M6 2H2v12h12v-4M10 2h4v4M7 9l7-7" />
              </svg>
              View in source
            </a>
          </section>
        )}
      </div>
    </div>
  );
}
