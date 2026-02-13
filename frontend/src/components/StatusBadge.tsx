import type { AlertStatus } from '../lib/types';

const STATUS_CONFIG: Record<AlertStatus, { bg: string; text: string; label: string }> = {
  firing:       { bg: 'bg-red-500/10 border border-red-500/20', text: 'text-red-400', label: 'Firing' },
  acknowledged: { bg: 'bg-amber-500/10 border border-amber-500/20', text: 'text-amber-400', label: 'Acked' },
  resolved:     { bg: 'bg-emerald-500/10 border border-emerald-500/20', text: 'text-emerald-400', label: 'Resolved' },
  suppressed:   { bg: 'bg-gray-500/10 border border-gray-500/20', text: 'text-gray-400', label: 'Suppressed' },
  archived:     { bg: 'bg-slate-500/10 border border-slate-500/20', text: 'text-slate-400', label: 'Archived' },
};

export function StatusBadge({ status }: { status: AlertStatus }) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.firing;

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${config.bg} ${config.text}`}>
      {config.label}
    </span>
  );
}
