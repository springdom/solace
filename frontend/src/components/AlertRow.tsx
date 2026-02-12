import type { Alert } from '../lib/types';
import { SeverityBadge } from './SeverityBadge';
import { StatusBadge } from './StatusBadge';
import { timeAgo, duration } from '../lib/time';

interface AlertRowProps {
  alert: Alert;
  selected: boolean;
  onSelect: (alert: Alert) => void;
  onAcknowledge: (id: string) => void;
  onResolve: (id: string) => void;
}

export function AlertRow({ alert, selected, onSelect, onAcknowledge, onResolve }: AlertRowProps) {
  const isFiring = alert.status === 'firing';
  const isCriticalFiring = isFiring && alert.severity === 'critical';

  return (
    <div
      onClick={() => onSelect(alert)}
      className={`
        group flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors border-l-2
        ${selected
          ? 'bg-solace-surface/80 border-l-blue-500'
          : 'border-l-transparent hover:bg-solace-surface/40'
        }
        ${isCriticalFiring ? 'severity-pulse-critical' : ''}
      `}
    >
      {/* Severity */}
      <div className="flex-shrink-0 w-16">
        <SeverityBadge severity={alert.severity} pulse={isFiring} />
      </div>

      {/* Main content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-medium text-solace-bright truncate">
            {alert.name}
          </span>
          {alert.duplicate_count > 1 && (
            <span className="flex-shrink-0 px-1.5 py-0.5 rounded bg-solace-border text-[10px] font-mono text-solace-muted">
              ×{alert.duplicate_count}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          {alert.service && (
            <span className="text-xs text-solace-muted font-mono">{alert.service}</span>
          )}
          {alert.service && alert.host && (
            <span className="text-solace-border">·</span>
          )}
          {alert.host && (
            <span className="text-xs text-solace-muted font-mono">{alert.host}</span>
          )}
        </div>
      </div>

      {/* Status */}
      <div className="flex-shrink-0">
        <StatusBadge status={alert.status} />
      </div>

      {/* Duration / Time */}
      <div className="flex-shrink-0 w-20 text-right">
        <div className="text-xs font-mono text-solace-muted">
          {alert.status === 'resolved'
            ? duration(alert.starts_at, alert.ends_at)
            : timeAgo(alert.starts_at)
          }
        </div>
      </div>

      {/* Actions */}
      <div className="flex-shrink-0 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        {alert.status === 'firing' && (
          <button
            onClick={(e) => { e.stopPropagation(); onAcknowledge(alert.id); }}
            className="px-2 py-1 text-xs font-medium rounded bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 transition-colors"
            title="Acknowledge"
          >
            ACK
          </button>
        )}
        {(alert.status === 'firing' || alert.status === 'acknowledged') && (
          <button
            onClick={(e) => { e.stopPropagation(); onResolve(alert.id); }}
            className="px-2 py-1 text-xs font-medium rounded bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors"
            title="Resolve"
          >
            RESOLVE
          </button>
        )}
      </div>
    </div>
  );
}
