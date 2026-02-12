import { useState, useMemo } from 'react';
import type { Alert, Incident, Severity } from './lib/types';
import { useAlerts } from './hooks/useAlerts';
import { useIncidents } from './hooks/useIncidents';
import { AlertRow } from './components/AlertRow';
import { AlertDetail } from './components/AlertDetail';
import { IncidentRow } from './components/IncidentRow';
import { IncidentDetail } from './components/IncidentDetail';
import { SearchBar } from './components/SearchBar';
import { SortControl } from './components/SortControl';
import { Pagination } from './components/Pagination';
import { StatsBar } from './components/StatsBar';
import { ColumnHeader } from './components/ColumnHeader';
import { useStats } from './hooks/useStats';
import type { SortOption } from './components/SortControl';

type View = 'alerts' | 'incidents';

const ALERT_STATUS_TABS = [
  { key: '', label: 'All' },
  { key: 'firing', label: 'Firing' },
  { key: 'acknowledged', label: 'Acknowledged' },
  { key: 'resolved', label: 'Resolved' },
] as const;

const INCIDENT_STATUS_TABS = [
  { key: '', label: 'All' },
  { key: 'open', label: 'Open' },
  { key: 'acknowledged', label: 'Acknowledged' },
  { key: 'resolved', label: 'Resolved' },
] as const;

const ALERT_SORT_OPTIONS: SortOption[] = [
  { value: 'created_at', label: 'Time' },
  { value: 'severity', label: 'Severity' },
  { value: 'name', label: 'Name' },
  { value: 'service', label: 'Service' },
  { value: 'duplicate_count', label: 'Duplicates' },
  { value: 'status', label: 'Status' },
];

const INCIDENT_SORT_OPTIONS: SortOption[] = [
  { value: 'started_at', label: 'Time' },
  { value: 'severity', label: 'Severity' },
  { value: 'title', label: 'Title' },
  { value: 'status', label: 'Status' },
];

const SEVERITY_FILTERS: { key: Severity; label: string; color: string; activeColor: string }[] = [
  { key: 'critical', label: 'CRIT', color: 'text-solace-muted', activeColor: 'text-red-400 bg-red-500/10 border-red-500/30' },
  { key: 'high', label: 'HIGH', color: 'text-solace-muted', activeColor: 'text-orange-400 bg-orange-500/10 border-orange-500/30' },
  { key: 'warning', label: 'WARN', color: 'text-solace-muted', activeColor: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30' },
  { key: 'low', label: 'LOW', color: 'text-solace-muted', activeColor: 'text-blue-400 bg-blue-500/10 border-blue-500/30' },
  { key: 'info', label: 'INFO', color: 'text-solace-muted', activeColor: 'text-gray-400 bg-gray-500/10 border-gray-500/30' },
];

const PAGE_SIZE = 25;

function SeverityCount({ severity, count }: { severity: Severity; count: number }) {
  const colors: Record<Severity, string> = {
    critical: 'text-red-400 bg-red-500/10',
    high: 'text-orange-400 bg-orange-500/10',
    warning: 'text-yellow-400 bg-yellow-500/10',
    low: 'text-blue-400 bg-blue-500/10',
    info: 'text-gray-400 bg-gray-500/10',
  };
  if (count === 0) return null;
  return (
    <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md ${colors[severity]}`}>
      <span className="text-lg font-mono font-bold">{count}</span>
      <span className="text-[10px] uppercase tracking-wider font-medium opacity-70">{severity}</span>
    </div>
  );
}

export default function App() {
  // View state
  const [view, setView] = useState<View>('incidents');

  // Alert controls
  const [alertStatus, setAlertStatus] = useState('');
  const [alertSeverity, setAlertSeverity] = useState('');
  const [alertSearch, setAlertSearch] = useState('');
  const [alertSortBy, setAlertSortBy] = useState('created_at');
  const [alertSortOrder, setAlertSortOrder] = useState<'asc' | 'desc'>('desc');
  const [alertPage, setAlertPage] = useState(1);
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);

  // Incident controls
  const [incidentStatus, setIncidentStatus] = useState('');
  const [incidentSearch, setIncidentSearch] = useState('');
  const [incidentSortBy, setIncidentSortBy] = useState('started_at');
  const [incidentSortOrder, setIncidentSortOrder] = useState<'asc' | 'desc'>('desc');
  const [incidentPage, setIncidentPage] = useState(1);
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);

  // Hooks
  const alertsHook = useAlerts({
    status: alertStatus || undefined,
    severity: alertSeverity || undefined,
    search: alertSearch || undefined,
    sortBy: alertSortBy,
    sortOrder: alertSortOrder,
    page: alertPage,
    pageSize: PAGE_SIZE,
  });

  const incidentsHook = useIncidents({
    status: incidentStatus || undefined,
    search: incidentSearch || undefined,
    sortBy: incidentSortBy,
    sortOrder: incidentSortOrder,
    page: incidentPage,
    pageSize: PAGE_SIZE,
  });

  // Stats for header + stats bar
  const { stats } = useStats();

  const severityCounts = useMemo(() => {
    if (!stats) return { critical: 0, high: 0, warning: 0, low: 0, info: 0 };
    return {
      critical: stats.alerts.by_severity.critical || 0,
      high: stats.alerts.by_severity.high || 0,
      warning: stats.alerts.by_severity.warning || 0,
      low: stats.alerts.by_severity.low || 0,
      info: stats.alerts.by_severity.info || 0,
    };
  }, [stats]);

  const activeCount = stats?.alerts.active || 0;

  // Handlers
  const handleAlertAck = async (id: string) => {
    await alertsHook.acknowledge(id);
    if (selectedAlert?.id === id) {
      setSelectedAlert(prev => prev ? { ...prev, status: 'acknowledged', acknowledged_at: new Date().toISOString() } : null);
    }
  };

  const handleAlertResolve = async (id: string) => {
    await alertsHook.resolve(id);
    if (selectedAlert?.id === id) {
      setSelectedAlert(prev => prev ? { ...prev, status: 'resolved', resolved_at: new Date().toISOString() } : null);
    }
  };

  const handleIncidentAck = async (id: string) => {
    await incidentsHook.acknowledge(id);
    alertsHook.refetch();
    if (selectedIncident?.id === id) {
      setSelectedIncident(prev => prev ? { ...prev, status: 'acknowledged', acknowledged_at: new Date().toISOString() } : null);
    }
  };

  const handleIncidentResolve = async (id: string) => {
    await incidentsHook.resolve(id);
    alertsHook.refetch();
    if (selectedIncident?.id === id) {
      setSelectedIncident(prev => prev ? { ...prev, status: 'resolved', resolved_at: new Date().toISOString() } : null);
    }
  };

  const switchView = (newView: View) => {
    setView(newView);
    setSelectedAlert(null);
    setSelectedIncident(null);
  };

  const resetAlertFilters = () => {
    setAlertStatus('');
    setAlertSeverity('');
    setAlertSearch('');
    setAlertSortBy('created_at');
    setAlertSortOrder('desc');
    setAlertPage(1);
    setSelectedAlert(null);
  };

  const resetIncidentFilters = () => {
    setIncidentStatus('');
    setIncidentSearch('');
    setIncidentSortBy('started_at');
    setIncidentSortOrder('desc');
    setIncidentPage(1);
    setSelectedIncident(null);
  };

  const hasAlertFilters = !!(alertStatus || alertSeverity || alertSearch || alertSortBy !== 'created_at');
  const hasIncidentFilters = !!(incidentStatus || incidentSearch || incidentSortBy !== 'started_at');

  const openIncidentCount = stats?.incidents.by_status.open || 0;

  return (
    <div className="h-screen flex flex-col bg-solace-bg">
      {/* ─── Header ─────────────────────────────────────── */}
      <header className="flex-shrink-0 flex items-center justify-between px-5 py-3 border-b border-solace-border bg-solace-bg">
        <div className="flex items-center gap-4">
          {/* Logo */}
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-md bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center">
              <svg width="14" height="14" viewBox="0 0 16 16" fill="white">
                <path d="M8 1a7 7 0 100 14A7 7 0 008 1zm0 2.5a1 1 0 110 2 1 1 0 010-2zM6.5 7h3l-.5 5.5h-2L6.5 7z" />
              </svg>
            </div>
            <span className="text-base font-semibold text-solace-bright tracking-tight">Solace</span>
          </div>

          <div className="w-px h-5 bg-solace-border" />

          {/* View toggle */}
          <div className="flex items-center bg-solace-surface rounded-lg p-0.5">
            <button
              onClick={() => switchView('incidents')}
              className={`
                relative px-3 py-1.5 text-xs font-medium rounded-md transition-colors
                ${view === 'incidents'
                  ? 'bg-solace-bg text-solace-bright shadow-sm'
                  : 'text-solace-muted hover:text-solace-text'
                }
              `}
            >
              Incidents
              {openIncidentCount > 0 && (
                <span className="ml-1.5 inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full bg-red-500/20 text-red-400 text-[10px] font-mono font-bold">
                  {openIncidentCount}
                </span>
              )}
            </button>
            <button
              onClick={() => switchView('alerts')}
              className={`
                px-3 py-1.5 text-xs font-medium rounded-md transition-colors
                ${view === 'alerts'
                  ? 'bg-solace-bg text-solace-bright shadow-sm'
                  : 'text-solace-muted hover:text-solace-text'
                }
              `}
            >
              Alerts
            </button>
          </div>

          <div className="w-px h-5 bg-solace-border" />

          {/* Severity counts */}
          <div className="flex items-center gap-2">
            <SeverityCount severity="critical" count={severityCounts.critical} />
            <SeverityCount severity="high" count={severityCounts.high} />
            <SeverityCount severity="warning" count={severityCounts.warning} />
            <SeverityCount severity="low" count={severityCounts.low} />
            <SeverityCount severity="info" count={severityCounts.info} />
            {activeCount === 0 && stats && (
              <span className="text-sm text-emerald-400 font-medium">All clear</span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-solace-muted font-mono">
            {view === 'incidents'
              ? `${incidentsHook.total} incident${incidentsHook.total !== 1 ? 's' : ''}`
              : `${alertsHook.total} alert${alertsHook.total !== 1 ? 's' : ''}`
            }
          </span>
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse-dot" title="Connected" />
        </div>
      </header>

      {/* ─── Toolbar: Status tabs + Search + Sort ───────── */}
      <div className="flex-shrink-0 flex items-center justify-between px-5 py-2 border-b border-solace-border bg-solace-bg gap-3">
        {/* Left: Status tabs + severity pills (alerts only) */}
        <div className="flex items-center gap-1 flex-wrap">
          {view === 'alerts' ? (
            <>
              {ALERT_STATUS_TABS.map(tab => (
                <button
                  key={tab.key}
                  onClick={() => { setAlertStatus(tab.key); setAlertPage(1); setSelectedAlert(null); }}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                    alertStatus === tab.key
                      ? 'bg-solace-surface text-solace-bright'
                      : 'text-solace-muted hover:text-solace-text hover:bg-solace-surface/50'
                  }`}
                >
                  {tab.label}
                </button>
              ))}

              <div className="w-px h-4 bg-solace-border mx-1" />

              {SEVERITY_FILTERS.map(sev => (
                <button
                  key={sev.key}
                  onClick={() => {
                    setAlertSeverity(alertSeverity === sev.key ? '' : sev.key);
                    setAlertPage(1);
                    setSelectedAlert(null);
                  }}
                  className={`
                    px-2 py-1 text-[10px] font-mono font-bold rounded border transition-colors
                    ${alertSeverity === sev.key
                      ? sev.activeColor
                      : 'border-transparent text-solace-muted hover:text-solace-text'
                    }
                  `}
                >
                  {sev.label}
                </button>
              ))}
            </>
          ) : (
            INCIDENT_STATUS_TABS.map(tab => (
              <button
                key={tab.key}
                onClick={() => { setIncidentStatus(tab.key); setIncidentPage(1); setSelectedIncident(null); }}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  incidentStatus === tab.key
                    ? 'bg-solace-surface text-solace-bright'
                    : 'text-solace-muted hover:text-solace-text hover:bg-solace-surface/50'
                }`}
              >
                {tab.label}
              </button>
            ))
          )}

          {/* Clear filters */}
          {view === 'alerts' && hasAlertFilters && (
            <button
              onClick={resetAlertFilters}
              className="ml-1 px-2 py-1 text-[10px] font-mono text-solace-muted hover:text-solace-text transition-colors"
            >
              Clear
            </button>
          )}
          {view === 'incidents' && hasIncidentFilters && (
            <button
              onClick={resetIncidentFilters}
              className="ml-1 px-2 py-1 text-[10px] font-mono text-solace-muted hover:text-solace-text transition-colors"
            >
              Clear
            </button>
          )}
        </div>

        {/* Right: Search + Sort */}
        <div className="flex items-center gap-2">
          <SearchBar
            value={view === 'alerts' ? alertSearch : incidentSearch}
            onChange={v => {
              if (view === 'alerts') { setAlertSearch(v); setAlertPage(1); }
              else { setIncidentSearch(v); setIncidentPage(1); }
            }}
            placeholder={view === 'alerts' ? 'Search alerts...' : 'Search incidents...'}
          />
          <SortControl
            options={view === 'alerts' ? ALERT_SORT_OPTIONS : INCIDENT_SORT_OPTIONS}
            sortBy={view === 'alerts' ? alertSortBy : incidentSortBy}
            sortOrder={view === 'alerts' ? alertSortOrder : incidentSortOrder}
            onSort={(by, order) => {
              if (view === 'alerts') { setAlertSortBy(by); setAlertSortOrder(order); setAlertPage(1); }
              else { setIncidentSortBy(by); setIncidentSortOrder(order); setIncidentPage(1); }
            }}
          />
        </div>
      </div>

      {/* ─── Stats Bar ──────────────────────────────────── */}
      <StatsBar stats={stats} />

      {/* ─── Body ───────────────────────────────────────── */}
      <div className="flex-1 flex min-h-0">
        {/* List */}
        <div className="flex-1 flex flex-col min-h-0">
          {/* Column headers */}
          {view === 'alerts' ? (
            <div className="flex-shrink-0 flex items-center gap-3 px-5 py-2 border-b border-solace-border bg-solace-surface/20">
              <div className="w-16">
                <ColumnHeader label="Severity" sortKey="severity" currentSort={alertSortBy} currentOrder={alertSortOrder}
                  onSort={k => { setAlertSortBy(k); setAlertSortOrder(alertSortBy === k && alertSortOrder === 'desc' ? 'asc' : 'desc'); setAlertPage(1); }} />
              </div>
              <div className="flex-1 min-w-0">
                <ColumnHeader label="Name" sortKey="name" currentSort={alertSortBy} currentOrder={alertSortOrder}
                  onSort={k => { setAlertSortBy(k); setAlertSortOrder(alertSortBy === k && alertSortOrder === 'desc' ? 'asc' : 'desc'); setAlertPage(1); }} />
              </div>
              <div className="w-28">
                <ColumnHeader label="Service" sortKey="service" currentSort={alertSortBy} currentOrder={alertSortOrder}
                  onSort={k => { setAlertSortBy(k); setAlertSortOrder(alertSortBy === k && alertSortOrder === 'desc' ? 'asc' : 'desc'); setAlertPage(1); }} />
              </div>
              <div className="w-24">
                <ColumnHeader label="Status" sortKey="status" currentSort={alertSortBy} currentOrder={alertSortOrder}
                  onSort={k => { setAlertSortBy(k); setAlertSortOrder(alertSortBy === k && alertSortOrder === 'desc' ? 'asc' : 'desc'); setAlertPage(1); }} />
              </div>
              <div className="w-16 text-right">
                <ColumnHeader label="Dupes" sortKey="duplicate_count" currentSort={alertSortBy} currentOrder={alertSortOrder}
                  onSort={k => { setAlertSortBy(k); setAlertSortOrder(alertSortBy === k && alertSortOrder === 'desc' ? 'asc' : 'desc'); setAlertPage(1); }} className="justify-end" />
              </div>
              <div className="w-24 text-right">
                <ColumnHeader label="Time" sortKey="created_at" currentSort={alertSortBy} currentOrder={alertSortOrder}
                  onSort={k => { setAlertSortBy(k); setAlertSortOrder(alertSortBy === k && alertSortOrder === 'desc' ? 'asc' : 'desc'); setAlertPage(1); }} className="justify-end" />
              </div>
            </div>
          ) : (
            <div className="flex-shrink-0 flex items-center gap-3 px-5 py-2 border-b border-solace-border bg-solace-surface/20">
              <div className="w-16">
                <ColumnHeader label="Severity" sortKey="severity" currentSort={incidentSortBy} currentOrder={incidentSortOrder}
                  onSort={k => { setIncidentSortBy(k); setIncidentSortOrder(incidentSortBy === k && incidentSortOrder === 'desc' ? 'asc' : 'desc'); setIncidentPage(1); }} />
              </div>
              <div className="flex-1 min-w-0">
                <ColumnHeader label="Title" sortKey="title" currentSort={incidentSortBy} currentOrder={incidentSortOrder}
                  onSort={k => { setIncidentSortBy(k); setIncidentSortOrder(incidentSortBy === k && incidentSortOrder === 'desc' ? 'asc' : 'desc'); setIncidentPage(1); }} />
              </div>
              <div className="w-24">
                <ColumnHeader label="Status" sortKey="status" currentSort={incidentSortBy} currentOrder={incidentSortOrder}
                  onSort={k => { setIncidentSortBy(k); setIncidentSortOrder(incidentSortBy === k && incidentSortOrder === 'desc' ? 'asc' : 'desc'); setIncidentPage(1); }} />
              </div>
              <div className="w-20 text-center">
                <span className="text-[10px] uppercase tracking-wider font-semibold text-solace-muted">Alerts</span>
              </div>
              <div className="w-24 text-right">
                <ColumnHeader label="Started" sortKey="started_at" currentSort={incidentSortBy} currentOrder={incidentSortOrder}
                  onSort={k => { setIncidentSortBy(k); setIncidentSortOrder(incidentSortBy === k && incidentSortOrder === 'desc' ? 'asc' : 'desc'); setIncidentPage(1); }} className="justify-end" />
              </div>
            </div>
          )}

          <div className="flex-1 overflow-y-auto">
            {view === 'alerts' ? (
              <>
                {alertsHook.loading && alertsHook.alerts.length === 0 && (
                  <div className="flex items-center justify-center h-40">
                    <div className="text-sm text-solace-muted">Loading alerts...</div>
                  </div>
                )}
                {alertsHook.error && (
                  <div className="m-4 p-3 rounded-md bg-red-500/10 border border-red-500/20 text-sm text-red-400">
                    {alertsHook.error}
                  </div>
                )}
                {!alertsHook.loading && alertsHook.alerts.length === 0 && (
                  <EmptyState label={alertSearch ? `No alerts matching "${alertSearch}"` : 'No alerts found'} />
                )}
                <div className="divide-y divide-solace-border/50">
                  {alertsHook.alerts.map(alert => (
                    <AlertRow
                      key={alert.id}
                      alert={alert}
                      selected={selectedAlert?.id === alert.id}
                      onSelect={setSelectedAlert}
                      onAcknowledge={handleAlertAck}
                      onResolve={handleAlertResolve}
                    />
                  ))}
                </div>
              </>
            ) : (
              <>
                {incidentsHook.loading && incidentsHook.incidents.length === 0 && (
                  <div className="flex items-center justify-center h-40">
                    <div className="text-sm text-solace-muted">Loading incidents...</div>
                  </div>
                )}
                {incidentsHook.error && (
                  <div className="m-4 p-3 rounded-md bg-red-500/10 border border-red-500/20 text-sm text-red-400">
                    {incidentsHook.error}
                  </div>
                )}
                {!incidentsHook.loading && incidentsHook.incidents.length === 0 && (
                  <EmptyState label={incidentSearch ? `No incidents matching "${incidentSearch}"` : 'No incidents found'} />
                )}
                <div className="divide-y divide-solace-border/50">
                  {incidentsHook.incidents.map(incident => (
                    <IncidentRow
                      key={incident.id}
                      incident={incident}
                      selected={selectedIncident?.id === incident.id}
                      onSelect={setSelectedIncident}
                      onAcknowledge={handleIncidentAck}
                      onResolve={handleIncidentResolve}
                    />
                  ))}
                </div>
              </>
            )}
          </div>

          {/* Pagination */}
          {view === 'alerts' ? (
            <Pagination
              page={alertPage}
              pageSize={PAGE_SIZE}
              total={alertsHook.total}
              onPageChange={setAlertPage}
            />
          ) : (
            <Pagination
              page={incidentPage}
              pageSize={PAGE_SIZE}
              total={incidentsHook.total}
              onPageChange={setIncidentPage}
            />
          )}
        </div>

        {/* Detail panel */}
        {view === 'alerts' && selectedAlert && (
          <div className="w-[400px] flex-shrink-0">
            <AlertDetail
              alert={selectedAlert}
              onAcknowledge={handleAlertAck}
              onResolve={handleAlertResolve}
              onClose={() => setSelectedAlert(null)}
            />
          </div>
        )}
        {view === 'incidents' && selectedIncident && (
          <div className="w-[420px] flex-shrink-0">
            <IncidentDetail
              incident={selectedIncident}
              onAcknowledge={handleIncidentAck}
              onResolve={handleIncidentResolve}
              onClose={() => setSelectedIncident(null)}
            />
          </div>
        )}
      </div>
    </div>
  );
}

function EmptyState({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-40 text-solace-muted">
      <svg width="32" height="32" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="mb-2 opacity-30">
        <circle cx="8" cy="8" r="6.5" />
        <path d="M5.5 9.5s1 1.5 2.5 1.5 2.5-1.5 2.5-1.5M6 6.5h.01M10 6.5h.01" />
      </svg>
      <span className="text-sm">{label}</span>
    </div>
  );
}
