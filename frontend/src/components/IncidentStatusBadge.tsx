import type { IncidentStatus } from '../lib/types';

const STATUS_CONFIG: Record<IncidentStatus, { bg: string; text: string; label: string }> = {
  open:         { bg: 'bg-red-500/10 border border-red-500/20', text: 'text-red-400', label: 'Open' },
  acknowledged: { bg: 'bg-amber-500/10 border border-amber-500/20', text: 'text-amber-400', label: 'Acked' },
  resolved:     { bg: 'bg-emerald-500/10 border border-emerald-500/20', text: 'text-emerald-400', label: 'Resolved' },
};

export function IncidentStatusBadge({ status }: { status: IncidentStatus }) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.open;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${config.bg} ${config.text}`}>
      {config.label}
    </span>
  );
}
