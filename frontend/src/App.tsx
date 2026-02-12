import { useState, useMemo, useCallback, useEffect } from 'react';
import type { Severity } from './lib/types';
import { api } from './lib/api';
import { useAlertStore } from './stores/alertStore';
import { useIncidentStore } from './stores/incidentStore';
import { useStatsStore } from './stores/statsStore';
import { useWSStore } from './stores/wsStore';
import { AlertRow } from './components/AlertRow';
import { AlertDetail } from './components/AlertDetail';
import { IncidentRow } from './components/IncidentRow';
import { IncidentDetail } from './components/IncidentDetail';
import { SearchBar } from './components/SearchBar';
import { SortControl } from './components/SortControl';
import { Pagination } from './components/Pagination';
import { StatsBar } from './components/StatsBar';
import { ColumnHeader } from './components/ColumnHeader';
import { SilenceList } from './components/SilenceList';
import { NotificationChannelList } from './components/NotificationChannelList';
import type { SortOption } from './components/SortControl';

type View = 'alerts' | 'incidents' | 'silences' | 'channels';

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
  // Initialize WebSocket + polling + initial data load
  const wsInit = useWSStore((s) => s.init);
  const wsCleanup = useWSStore((s) => s.cleanup);
  const wsConnected = useWSStore((s) => s.connected);

  useEffect(() => {
    wsInit();
    return wsCleanup;
  }, [wsInit, wsCleanup]);

  // View state (local — purely UI)
  const [view, setView] = useState<View>('incidents');

  // Alert store
  const alerts = useAlertStore((s) => s.alerts);
  const alertTotal = useAlertStore((s) => s.total);
  const alertLoading = useAlertStore((s) => s.loading);
  const alertError = useAlertStore((s) => s.error);
  const alertFilters = useAlertStore((s) => s.filters);
  const selectedAlert = useAlertStore((s) => s.selectedAlert);
  const setAlertFilters = useAlertStore((s) => s.setFilters);
  const resetAlertFilters = useAlertStore((s) => s.resetFilters);
  const selectAlert = useAlertStore((s) => s.selectAlert);
  const acknowledgeAlert = useAlertStore((s) => s.acknowledge);
  const resolveAlert = useAlertStore((s) => s.resolve);
  const addTag = useAlertStore((s) => s.addTag);
  const removeTag = useAlertStore((s) => s.removeTag);
  const refetchAlerts = useAlertStore((s) => s.fetchAlerts);

  // Incident store
  const incidents = useIncidentStore((s) => s.incidents);
  const incidentTotal = useIncidentStore((s) => s.total);
  const incidentLoading = useIncidentStore((s) => s.loading);
  const incidentError = useIncidentStore((s) => s.error);
  const incidentFilters = useIncidentStore((s) => s.filters);
  const selectedIncident = useIncidentStore((s) => s.selectedIncident);
  const setIncidentFilters = useIncidentStore((s) => s.setFilters);
  const resetIncidentFilters = useIncidentStore((s) => s.resetFilters);
  const selectIncident = useIncidentStore((s) => s.selectIncident);
  const acknowledgeIncident = useIncidentStore((s) => s.acknowledge);
  const resolveIncident = useIncidentStore((s) => s.resolve);

  // Stats store
  const stats = useStatsStore((s) => s.stats);

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
  const openIncidentCount = stats?.incidents.by_status.open || 0;

  // Handlers
  const handleAlertAck = async (id: string) => {
    await acknowledgeAlert(id);
  };

  const handleAlertResolve = async (id: string) => {
    await resolveAlert(id);
  };

  const handleIncidentAck = async (id: string) => {
    await acknowledgeIncident(id);
    refetchAlerts();
  };

  const handleIncidentResolve = async (id: string) => {
    await resolveIncident(id);
    refetchAlerts();
  };

  const handleAlertSelectFromIncident = useCallback(async (alertId: string) => {
    try {
      const alert = await api.alerts.get(alertId);
      selectAlert(alert);
    } catch {
      // Alert may have been deleted
    }
  }, [selectAlert]);

  const switchView = (newView: View) => {
    setView(newView);
    selectAlert(null);
    selectIncident(null);
  };

  const hasAlertFilters = !!(alertFilters.status || alertFilters.severity || alertFilters.search || alertFilters.sortBy !== 'created_at');
  const hasIncidentFilters = !!(incidentFilters.status || incidentFilters.search || incidentFilters.sortBy !== 'started_at');

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
            <button
              onClick={() => switchView('silences')}
              className={`
                px-3 py-1.5 text-xs font-medium rounded-md transition-colors
                ${view === 'silences'
                  ? 'bg-solace-bg text-solace-bright shadow-sm'
                  : 'text-solace-muted hover:text-solace-text'
                }
              `}
            >
              Silences
            </button>
            <button
              onClick={() => switchView('channels')}
              className={`
                px-3 py-1.5 text-xs font-medium rounded-md transition-colors
                ${view === 'channels'
                  ? 'bg-solace-bg text-solace-bright shadow-sm'
                  : 'text-solace-muted hover:text-solace-text'
                }
              `}
            >
              Channels
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
              ? `${incidentTotal} incident${incidentTotal !== 1 ? 's' : ''}`
              : view === 'alerts'
              ? `${alertTotal} alert${alertTotal !== 1 ? 's' : ''}`
              : null
            }
          </span>
          <div className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-emerald-500 animate-pulse-dot' : 'bg-yellow-500'}`} title={wsConnected ? 'Connected' : 'Reconnecting...'} />
        </div>
      </header>

      {/* ─── Toolbar: Status tabs + Search + Sort ───────── */}
      {(view === 'alerts' || view === 'incidents') && <div className="flex-shrink-0 flex items-center justify-between px-5 py-2 border-b border-solace-border bg-solace-bg gap-3">
        {/* Left: Status tabs + severity pills (alerts only) */}
        <div className="flex items-center gap-1 flex-wrap">
          {view === 'alerts' ? (
            <>
              {ALERT_STATUS_TABS.map(tab => (
                <button
                  key={tab.key}
                  onClick={() => { setAlertFilters({ status: tab.key || undefined, page: 1 }); selectAlert(null); }}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                    (alertFilters.status || '') === tab.key
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
                    setAlertFilters({ severity: alertFilters.severity === sev.key ? undefined : sev.key, page: 1 });
                    selectAlert(null);
                  }}
                  className={`
                    px-2 py-1 text-[10px] font-mono font-bold rounded border transition-colors
                    ${alertFilters.severity === sev.key
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
                onClick={() => { setIncidentFilters({ status: tab.key || undefined, page: 1 }); selectIncident(null); }}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  (incidentFilters.status || '') === tab.key
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
            value={view === 'alerts' ? (alertFilters.search || '') : (incidentFilters.search || '')}
            onChange={v => {
              if (view === 'alerts') { setAlertFilters({ search: v || undefined, page: 1 }); }
              else { setIncidentFilters({ search: v || undefined, page: 1 }); }
            }}
            placeholder={view === 'alerts' ? 'Search alerts...' : 'Search incidents...'}
          />
          <SortControl
            options={view === 'alerts' ? ALERT_SORT_OPTIONS : INCIDENT_SORT_OPTIONS}
            sortBy={view === 'alerts' ? alertFilters.sortBy : incidentFilters.sortBy}
            sortOrder={view === 'alerts' ? alertFilters.sortOrder : incidentFilters.sortOrder}
            onSort={(by, order) => {
              if (view === 'alerts') { setAlertFilters({ sortBy: by, sortOrder: order, page: 1 }); }
              else { setIncidentFilters({ sortBy: by, sortOrder: order, page: 1 }); }
            }}
          />
        </div>
      </div>

      }
      {/* ─── Stats Bar ──────────────────────────────────── */}
      {(view === 'alerts' || view === 'incidents') && <StatsBar stats={stats} />}

      {/* ─── Body ───────────────────────────────────────── */}
      {view === 'silences' ? (
        <div className="flex-1 min-h-0">
          <SilenceList />
        </div>
      ) : view === 'channels' ? (
        <div className="flex-1 min-h-0">
          <NotificationChannelList />
        </div>
      ) : (
      <div className="flex-1 flex min-h-0">
        {/* List */}
        <div className="flex-1 flex flex-col min-h-0">
          {/* Column headers */}
          {view === 'alerts' ? (
            <div className="flex-shrink-0 flex items-center gap-3 px-5 py-2 border-b border-solace-border bg-solace-surface/20">
              <div className="w-16">
                <ColumnHeader label="Severity" sortKey="severity" currentSort={alertFilters.sortBy} currentOrder={alertFilters.sortOrder}
                  onSort={k => { setAlertFilters({ sortBy: k, sortOrder: alertFilters.sortBy === k && alertFilters.sortOrder === 'desc' ? 'asc' : 'desc', page: 1 }); }} />
              </div>
              <div className="flex-1 min-w-0">
                <ColumnHeader label="Name" sortKey="name" currentSort={alertFilters.sortBy} currentOrder={alertFilters.sortOrder}
                  onSort={k => { setAlertFilters({ sortBy: k, sortOrder: alertFilters.sortBy === k && alertFilters.sortOrder === 'desc' ? 'asc' : 'desc', page: 1 }); }} />
              </div>
              <div className="w-28">
                <ColumnHeader label="Service" sortKey="service" currentSort={alertFilters.sortBy} currentOrder={alertFilters.sortOrder}
                  onSort={k => { setAlertFilters({ sortBy: k, sortOrder: alertFilters.sortBy === k && alertFilters.sortOrder === 'desc' ? 'asc' : 'desc', page: 1 }); }} />
              </div>
              <div className="w-24">
                <ColumnHeader label="Status" sortKey="status" currentSort={alertFilters.sortBy} currentOrder={alertFilters.sortOrder}
                  onSort={k => { setAlertFilters({ sortBy: k, sortOrder: alertFilters.sortBy === k && alertFilters.sortOrder === 'desc' ? 'asc' : 'desc', page: 1 }); }} />
              </div>
              <div className="w-16 text-right">
                <ColumnHeader label="Dupes" sortKey="duplicate_count" currentSort={alertFilters.sortBy} currentOrder={alertFilters.sortOrder}
                  onSort={k => { setAlertFilters({ sortBy: k, sortOrder: alertFilters.sortBy === k && alertFilters.sortOrder === 'desc' ? 'asc' : 'desc', page: 1 }); }} className="justify-end" />
              </div>
              <div className="w-24 text-right">
                <ColumnHeader label="Time" sortKey="created_at" currentSort={alertFilters.sortBy} currentOrder={alertFilters.sortOrder}
                  onSort={k => { setAlertFilters({ sortBy: k, sortOrder: alertFilters.sortBy === k && alertFilters.sortOrder === 'desc' ? 'asc' : 'desc', page: 1 }); }} className="justify-end" />
              </div>
            </div>
          ) : (
            <div className="flex-shrink-0 flex items-center gap-3 px-5 py-2 border-b border-solace-border bg-solace-surface/20">
              <div className="w-16">
                <ColumnHeader label="Severity" sortKey="severity" currentSort={incidentFilters.sortBy} currentOrder={incidentFilters.sortOrder}
                  onSort={k => { setIncidentFilters({ sortBy: k, sortOrder: incidentFilters.sortBy === k && incidentFilters.sortOrder === 'desc' ? 'asc' : 'desc', page: 1 }); }} />
              </div>
              <div className="flex-1 min-w-0">
                <ColumnHeader label="Title" sortKey="title" currentSort={incidentFilters.sortBy} currentOrder={incidentFilters.sortOrder}
                  onSort={k => { setIncidentFilters({ sortBy: k, sortOrder: incidentFilters.sortBy === k && incidentFilters.sortOrder === 'desc' ? 'asc' : 'desc', page: 1 }); }} />
              </div>
              <div className="w-24">
                <ColumnHeader label="Status" sortKey="status" currentSort={incidentFilters.sortBy} currentOrder={incidentFilters.sortOrder}
                  onSort={k => { setIncidentFilters({ sortBy: k, sortOrder: incidentFilters.sortBy === k && incidentFilters.sortOrder === 'desc' ? 'asc' : 'desc', page: 1 }); }} />
              </div>
              <div className="w-20 text-center">
                <span className="text-[10px] uppercase tracking-wider font-semibold text-solace-muted">Alerts</span>
              </div>
              <div className="w-24 text-right">
                <ColumnHeader label="Started" sortKey="started_at" currentSort={incidentFilters.sortBy} currentOrder={incidentFilters.sortOrder}
                  onSort={k => { setIncidentFilters({ sortBy: k, sortOrder: incidentFilters.sortBy === k && incidentFilters.sortOrder === 'desc' ? 'asc' : 'desc', page: 1 }); }} className="justify-end" />
              </div>
            </div>
          )}

          <div className="flex-1 overflow-y-auto">
            {view === 'alerts' ? (
              <>
                {alertLoading && alerts.length === 0 && (
                  <div className="flex items-center justify-center h-40">
                    <div className="text-sm text-solace-muted">Loading alerts...</div>
                  </div>
                )}
                {alertError && (
                  <div className="m-4 p-3 rounded-md bg-red-500/10 border border-red-500/20 text-sm text-red-400">
                    {alertError}
                  </div>
                )}
                {!alertLoading && alerts.length === 0 && (
                  <EmptyState label={alertFilters.search ? `No alerts matching "${alertFilters.search}"` : 'No alerts found'} />
                )}
                <div className="divide-y divide-solace-border/50">
                  {alerts.map(alert => (
                    <AlertRow
                      key={alert.id}
                      alert={alert}
                      selected={selectedAlert?.id === alert.id}
                      onSelect={selectAlert}
                      onAcknowledge={handleAlertAck}
                      onResolve={handleAlertResolve}
                    />
                  ))}
                </div>
              </>
            ) : (
              <>
                {incidentLoading && incidents.length === 0 && (
                  <div className="flex items-center justify-center h-40">
                    <div className="text-sm text-solace-muted">Loading incidents...</div>
                  </div>
                )}
                {incidentError && (
                  <div className="m-4 p-3 rounded-md bg-red-500/10 border border-red-500/20 text-sm text-red-400">
                    {incidentError}
                  </div>
                )}
                {!incidentLoading && incidents.length === 0 && (
                  <EmptyState label={incidentFilters.search ? `No incidents matching "${incidentFilters.search}"` : 'No incidents found'} />
                )}
                <div className="divide-y divide-solace-border/50">
                  {incidents.map(incident => (
                    <IncidentRow
                      key={incident.id}
                      incident={incident}
                      selected={selectedIncident?.id === incident.id}
                      onSelect={selectIncident}
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
              page={alertFilters.page}
              pageSize={alertFilters.pageSize}
              total={alertTotal}
              onPageChange={(p) => setAlertFilters({ page: p })}
            />
          ) : (
            <Pagination
              page={incidentFilters.page}
              pageSize={incidentFilters.pageSize}
              total={incidentTotal}
              onPageChange={(p) => setIncidentFilters({ page: p })}
            />
          )}
        </div>

        {/* Detail panel */}
        {/* Alert detail panel — shown in alerts view OR when drilled in from incident */}
        {selectedAlert && (
          <div className="w-[400px] flex-shrink-0">
            <AlertDetail
              alert={selectedAlert}
              onAcknowledge={handleAlertAck}
              onResolve={handleAlertResolve}
              onClose={() => selectAlert(null)}
              onTagAdd={async (alertId, tag) => {
                const updated = await addTag(alertId, tag);
                return updated;
              }}
              onTagRemove={async (alertId, tag) => {
                const updated = await removeTag(alertId, tag);
                return updated;
              }}
            />
          </div>
        )}
        {view === 'incidents' && selectedIncident && !selectedAlert && (
          <div className="w-[420px] flex-shrink-0">
            <IncidentDetail
              incident={selectedIncident}
              onAcknowledge={handleIncidentAck}
              onResolve={handleIncidentResolve}
              onClose={() => selectIncident(null)}
              onAlertSelect={handleAlertSelectFromIncident}
            />
          </div>
        )}
      </div>
      )}
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
