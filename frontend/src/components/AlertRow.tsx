import type { Alert } from '../lib/types';
import { SeverityBadge } from './SeverityBadge';
import { StatusBadge } from './StatusBadge';
import { timeAgo } from '../lib/time';

interface AlertRowProps {
  alert: Alert;
  selected: boolean;
  checked?: boolean;
  showCheckbox?: boolean;
  onSelect: (alert: Alert) => void;
  onAcknowledge?: (id: string) => void;
  onResolve?: (id: string) => void;
  onToggleCheck?: (id: string) => void;
}

export function AlertRow({ alert, selected, checked, showCheckbox, onSelect, onAcknowledge, onResolve, onToggleCheck }: AlertRowProps) {
  const isFiring = alert.status === 'firing';
  const isActive = isFiring || alert.status === 'acknowledged';
  const isCriticalFiring = isFiring && alert.severity === 'critical';

  return (
    <div
      onClick={() => onSelect(alert)}
      className={`
        group relative flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors border-l-2
        ${selected
          ? 'bg-solace-surface/80 border-l-blue-500'
          : 'border-l-transparent hover:bg-solace-surface/40'
        }
        ${isCriticalFiring ? 'severity-pulse-critical' : ''}
      `}
    >
      {/* Checkbox */}
      {showCheckbox && (
        <div className="flex-shrink-0" onClick={e => e.stopPropagation()}>
          <input
            type="checkbox"
            checked={checked || false}
            onChange={() => onToggleCheck?.(alert.id)}
            className="rounded border-solace-border bg-solace-bg text-blue-500 focus:ring-0 focus:ring-offset-0"
          />
        </div>
      )}

      {/* Severity — w-16 */}
      <div className="flex-shrink-0 w-16">
        <SeverityBadge severity={alert.severity} pulse={isFiring} />
      </div>

      {/* Name — flex-1 */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-medium text-solace-bright truncate">
            {alert.name}
          </span>
          {alert.tags.length > 0 && (
            <>
              {alert.tags.slice(0, 2).map(tag => (
                <span
                  key={tag}
                  className="flex-shrink-0 px-1.5 py-0 rounded-full bg-teal-500/10 text-teal-400 text-[10px] font-mono border border-teal-500/20 truncate max-w-[80px]"
                >
                  {tag}
                </span>
              ))}
              {alert.tags.length > 2 && (
                <span className="text-[10px] text-solace-muted font-mono">+{alert.tags.length - 2}</span>
              )}
            </>
          )}
        </div>
      </div>

      {/* Service — w-28 */}
      <div className="flex-shrink-0 w-28 truncate">
        <span className="text-xs text-solace-muted font-mono">
          {alert.service || '\u2014'}
        </span>
      </div>

      {/* Status — w-24 */}
      <div className="flex-shrink-0 w-24">
        <StatusBadge status={alert.status} />
      </div>

      {/* Dupes — w-16 */}
      <div className="flex-shrink-0 w-16 text-right">
        <span className="text-xs font-mono text-solace-muted">
          {alert.duplicate_count > 1 ? `x${alert.duplicate_count}` : ''}
        </span>
      </div>

      {/* Time — w-24 */}
      <div className="flex-shrink-0 w-24 text-right">
        <div className="text-xs font-mono text-solace-muted">
          {timeAgo(alert.starts_at)}
        </div>
      </div>

      {/* Actions — absolutely positioned so columns don't shift */}
      {isActive && (onAcknowledge || onResolve) && (
        <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity bg-solace-surface/95 backdrop-blur-sm rounded px-1 py-0.5">
          {isFiring && onAcknowledge && (
            <button
              onClick={(e) => { e.stopPropagation(); onAcknowledge(alert.id); }}
              className="px-2 py-1 text-xs font-medium rounded bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 transition-colors"
            >
              ACK
            </button>
          )}
          {onResolve && (
            <button
              onClick={(e) => { e.stopPropagation(); onResolve(alert.id); }}
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
