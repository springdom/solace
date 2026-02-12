import type { DashboardStats } from '../lib/api';

interface StatsBarProps {
  stats: DashboardStats | null;
}

function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return '—';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

export function StatsBar({ stats }: StatsBarProps) {
  if (!stats) return null;

  const items = [
    {
      label: 'Active',
      value: stats.alerts.active,
      color: stats.alerts.active > 0 ? 'text-red-400' : 'text-emerald-400',
    },
    {
      label: 'Open Incidents',
      value: stats.incidents.by_status.open || 0,
      color: (stats.incidents.by_status.open || 0) > 0 ? 'text-orange-400' : 'text-emerald-400',
    },
    { label: 'MTTA (24h)', value: formatDuration(stats.mtta_seconds), color: 'text-blue-400' },
    { label: 'MTTR (24h)', value: formatDuration(stats.mttr_seconds), color: 'text-purple-400' },
    { label: 'Total Alerts', value: stats.alerts.total, color: 'text-solace-text' },
    { label: 'Total Incidents', value: stats.incidents.total, color: 'text-solace-text' },
  ];

  return (
    <div className="flex items-center gap-5 px-5 py-2 border-b border-solace-border bg-solace-surface/30">
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-2">
          <span className="text-[10px] uppercase tracking-wider text-solace-muted font-medium">
            {item.label}
          </span>
          <span className={`text-sm font-mono font-semibold ${item.color}`}>
            {item.value}
          </span>
        </div>
      ))}
    </div>
  );
}
