import type { Incident } from '../lib/types';
import { SeverityBadge } from './SeverityBadge';
import { IncidentStatusBadge } from './IncidentStatusBadge';
import { timeAgo } from '../lib/time';

interface IncidentRowProps {
  incident: Incident;
  selected: boolean;
  onSelect: (incident: Incident) => void;
  onAcknowledge?: (id: string) => void;
  onResolve?: (id: string) => void;
}

export function IncidentRow({ incident, selected, onSelect, onAcknowledge, onResolve }: IncidentRowProps) {
  const isOpen = incident.status === 'open';
  const isActive = isOpen || incident.status === 'acknowledged';

  return (
    <div
      onClick={() => onSelect(incident)}
      className={`
        group relative flex items-center gap-3 px-4 py-3.5 cursor-pointer transition-colors border-l-2
        ${selected
          ? 'bg-solace-surface/80 border-l-blue-500'
          : 'border-l-transparent hover:bg-solace-surface/40'
        }
      `}
    >
      {/* Severity — w-16 */}
      <div className="flex-shrink-0 w-16">
        <SeverityBadge severity={incident.severity} pulse={isOpen} />
      </div>

      {/* Title — flex-1 */}
      <div className="flex-1 min-w-0">
        <span className="font-mono text-sm font-medium text-solace-bright truncate block">
          {incident.title}
        </span>
      </div>

      {/* Status — w-24 */}
      <div className="flex-shrink-0 w-24">
        <IncidentStatusBadge status={incident.status} />
      </div>

      {/* Alerts count — w-20 */}
      <div className="flex-shrink-0 w-20 text-center">
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-solace-border/50 text-[10px] font-mono text-solace-muted">
          <svg width="10" height="10" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M8 2L1 14h14L8 2z" />
          </svg>
          {incident.alert_count}
        </span>
      </div>

      {/* Started — w-24 */}
      <div className="flex-shrink-0 w-24 text-right">
        <div className="text-xs font-mono text-solace-muted">
          {timeAgo(incident.started_at)}
        </div>
      </div>

      {/* Actions — absolutely positioned so columns don't shift */}
      {isActive && (onAcknowledge || onResolve) && (
        <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity bg-solace-surface/95 backdrop-blur-sm rounded px-1 py-0.5">
          {isOpen && onAcknowledge && (
            <button
              onClick={(e) => { e.stopPropagation(); onAcknowledge(incident.id); }}
              className="px-2 py-1 text-xs font-medium rounded bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 transition-colors"
            >
              ACK
            </button>
          )}
          {onResolve && (
            <button
              onClick={(e) => { e.stopPropagation(); onResolve(incident.id); }}
              className="px-2 py-1 text-xs font-medium rounded bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors"
            >
              RESOLVE
            </button>
          )}
        </div>
      )}
    </div>
  );
}
