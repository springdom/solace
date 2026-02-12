import type { Severity } from '../lib/types';

const SEVERITY_CONFIG: Record<Severity, { bg: string; text: string; dot: string; label: string }> = {
  critical: { bg: 'bg-red-500/10', text: 'text-red-400', dot: 'bg-red-500', label: 'CRIT' },
  high:     { bg: 'bg-orange-500/10', text: 'text-orange-400', dot: 'bg-orange-500', label: 'HIGH' },
  warning:  { bg: 'bg-yellow-500/10', text: 'text-yellow-400', dot: 'bg-yellow-500', label: 'WARN' },
  low:      { bg: 'bg-blue-500/10', text: 'text-blue-400', dot: 'bg-blue-500', label: 'LOW' },
  info:     { bg: 'bg-gray-500/10', text: 'text-gray-400', dot: 'bg-gray-500', label: 'INFO' },
};

export function SeverityBadge({ severity, pulse }: { severity: Severity; pulse?: boolean }) {
  const config = SEVERITY_CONFIG[severity] || SEVERITY_CONFIG.info;

  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded font-mono text-xs font-medium ${config.bg} ${config.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${config.dot} ${pulse ? 'animate-pulse-dot' : ''}`} />
      {config.label}
    </span>
  );
}
