import { useState, useMemo, useCallback, useEffect } from 'react';
import type { Severity } from './lib/types';
import { api } from './lib/api';
import { useAlertStore } from './stores/alertStore';
import { useIncidentStore } from './stores/incidentStore';
import { useStatsStore } from './stores/statsStore';
import { useSettingsStore } from './stores/settingsStore';
import { useWSStore } from './stores/wsStore';
import { useAuthStore } from './stores/authStore';
import { useThemeStore } from './stores/themeStore';
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
import { LoginPage } from './components/LoginPage';
import { ChangePasswordPage } from './components/ChangePasswordPage';
import { UserManagement } from './components/UserManagement';
import { OnCallView } from './components/OnCallView';
import type { SortOption } from './components/SortControl';

type View = 'alerts' | 'incidents' | 'silences' | 'channels' | 'settings' | 'oncall' | 'users' | 'statistics';

const ALERT_STATUS_TABS = [
  { key: '', label: 'All' },
  { key: 'firing', label: 'Firing' },
  { key: 'acknowledged', label: 'Acknowledged' },
  { key: 'resolved', label: 'Resolved' },
  { key: 'archived', label: 'Archived' },
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

const ROLE_COLORS: Record<string, string> = {
  admin: 'bg-red-500/10 text-red-400 border-red-500/20',
  user: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  viewer: 'bg-gray-500/10 text-gray-400 border-gray-500/20',
};

export default function App() {
  const { isAuthenticated, mustChangePassword, loading: authLoading, user, logout } = useAuthStore();
  const loadFromStorage = useAuthStore((s) => s.loadFromStorage);
  const isRole = useAuthStore((s) => s.isRole);

  useEffect(() => {
    loadFromStorage();
  }, [loadFromStorage]);

  if (authLoading) {
    return (
      <div className="h-screen flex items-center justify-center bg-solace-bg">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 rounded-md bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center animate-pulse">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="white">
              <path d="M8 1a7 7 0 100 14A7 7 0 008 1zm0 2.5a1 1 0 110 2 1 1 0 010-2zM6.5 7h3l-.5 5.5h-2L6.5 7z" />
            </svg>
          </div>
          <span className="text-sm text-solace-muted">Loading...</span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  if (mustChangePassword) {
    return <ChangePasswordPage />;
  }

  return <Dashboard user={user!} logout={logout} isRole={isRole} />;
}

function Dashboard({ user, logout, isRole }: {
  user: import('./lib/types').UserProfile;
  logout: () => void;
  isRole: (...roles: import('./lib/types').UserRole[]) => boolean;
}) {
  const isAdmin = isRole('admin');
  const isViewer = isRole('viewer');

  // Theme
  const theme = useThemeStore((s) => s.theme);
  const toggleTheme = useThemeStore((s) => s.toggle);

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
  const [showShortcutHelp, setShowShortcutHelp] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);

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

  // Bulk selection
  const selectedIds = useAlertStore((s) => s.selectedIds);
  const toggleSelect = useAlertStore((s) => s.toggleSelect);
  const selectAll = useAlertStore((s) => s.selectAll);
  const clearSelection = useAlertStore((s) => s.clearSelection);
  const bulkAcknowledge = useAlertStore((s) => s.bulkAcknowledge);
  const bulkResolve = useAlertStore((s) => s.bulkResolve);

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

  // Settings store
  const settingsData = useSettingsStore((s) => s.settings);
  const settingsLoading = useSettingsStore((s) => s.loading);
  const fetchSettings = useSettingsStore((s) => s.fetchSettings);

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

  const handleTagClick = useCallback((tag: string) => {
    setAlertFilters({ tag, page: 1 });
  }, [setAlertFilters]);

  const switchView = (newView: View) => {
    setView(newView);
    selectAlert(null);
    selectIncident(null);
    clearSelection();
    if (newView === 'settings' && !settingsData) {
      fetchSettings();
    }
  };

  const hasAlertFilters = !!(alertFilters.status || alertFilters.severity || alertFilters.tag || alertFilters.search || alertFilters.sortBy !== 'created_at');
  const hasIncidentFilters = !!(incidentFilters.status || incidentFilters.search || incidentFilters.sortBy !== 'started_at');

  const hasBulkSelection = selectedIds.size > 0;

  // Archive action state
  const [archiveDays, setArchiveDays] = useState(30);
  const [archiveResult, setArchiveResult] = useState<string | null>(null);

  const handleArchive = async () => {
    try {
      const result = await api.alerts.archive(archiveDays);
      setArchiveResult(`Archived ${result.archived} alert(s)`);
      setTimeout(() => setArchiveResult(null), 3000);
    } catch {
      setArchiveResult('Archive failed');
      setTimeout(() => setArchiveResult(null), 3000);
    }
  };

  // Dynamic nav items based on role
  const navItems: { key: View; label: string }[] = [
    { key: 'incidents', label: 'Incidents' },
    { key: 'alerts', label: 'Alerts' },
    { key: 'oncall', label: 'On-Call' },
    { key: 'silences', label: 'Silences' },
    { key: 'channels', label: 'Channels' },
    { key: 'statistics', label: 'Statistics' },
    { key: 'settings', label: 'Settings' },
    ...(isAdmin ? [{ key: 'users' as View, label: 'Users' }] : []),
  ];

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Skip if typing in an input
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT') return;

      switch (e.key) {
        case '?':
          e.preventDefault();
          setShowShortcutHelp(prev => !prev);
          break;
        case 'Escape':
          if (showShortcutHelp) {
            setShowShortcutHelp(false);
          } else if (showUserMenu) {
            setShowUserMenu(false);
          } else if (selectedAlert) {
            selectAlert(null);
          } else if (selectedIncident) {
            selectIncident(null);
          }
          break;
        case 'a':
          if (isViewer) break;
          if (selectedAlert && selectedAlert.status === 'firing') {
            handleAlertAck(selectedAlert.id);
          } else if (selectedIncident && selectedIncident.status === 'open') {
            handleIncidentAck(selectedIncident.id);
          }
          break;
        case 'r':
          if (isViewer) break;
          if (selectedAlert && (selectedAlert.status === 'firing' || selectedAlert.status === 'acknowledged')) {
            handleAlertResolve(selectedAlert.id);
          } else if (selectedIncident && (selectedIncident.status === 'open' || selectedIncident.status === 'acknowledged')) {
            handleIncidentResolve(selectedIncident.id);
          }
          break;
        case 'j': {
          e.preventDefault();
          if (view === 'alerts') {
            const idx = alerts.findIndex(a => a.id === selectedAlert?.id);
            const next = alerts[idx + 1];
            if (next) selectAlert(next);
            else if (!selectedAlert && alerts.length > 0) selectAlert(alerts[0]);
          } else if (view === 'incidents') {
            const idx = incidents.findIndex(i => i.id === selectedIncident?.id);
            const next = incidents[idx + 1];
            if (next) selectIncident(next);
            else if (!selectedIncident && incidents.length > 0) selectIncident(incidents[0]);
          }
          break;
        }
        case 'k': {
          e.preventDefault();
          if (view === 'alerts') {
            const idx = alerts.findIndex(a => a.id === selectedAlert?.id);
            const prev = alerts[idx - 1];
            if (prev) selectAlert(prev);
          } else if (view === 'incidents') {
            const idx = incidents.findIndex(i => i.id === selectedIncident?.id);
            const prev = incidents[idx - 1];
            if (prev) selectIncident(prev);
          }
          break;
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [view, alerts, incidents, selectedAlert, selectedIncident, showShortcutHelp, showUserMenu, isViewer]);

  return (
    <div className="h-screen flex flex-col bg-solace-bg">
      {/* Keyboard shortcut help overlay */}
      {showShortcutHelp && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setShowShortcutHelp(false)}>
          <div className="bg-solace-surface border border-solace-border rounded-lg p-6 max-w-sm shadow-xl" onClick={e => e.stopPropagation()}>
            <h2 className="text-base font-semibold text-solace-bright mb-4">Keyboard Shortcuts</h2>
            <div className="space-y-2 text-sm">
              {[
                ['?', 'Toggle this help'],
                ['Esc', 'Close panel / dismiss'],
                ['a', 'Acknowledge selected'],
                ['r', 'Resolve selected'],
                ['j', 'Next item in list'],
                ['k', 'Previous item in list'],
              ].map(([key, desc]) => (
                <div key={key} className="flex items-center gap-3">
                  <kbd className="px-2 py-0.5 rounded bg-solace-bg border border-solace-border text-solace-bright font-mono text-xs min-w-[28px] text-center">{key}</kbd>
                  <span className="text-solace-text">{desc}</span>
                </div>
              ))}
            </div>
            <div className="mt-4 text-xs text-solace-muted">Press ? or click outside to close</div>
          </div>
        </div>
      )}

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
            {navItems.map(v => (
              <button
                key={v.key}
                onClick={() => switchView(v.key)}
                className={`
                  px-3 py-1.5 text-xs font-medium rounded-md transition-colors
                  ${view === v.key
                    ? 'bg-solace-bg text-solace-bright shadow-sm'
                    : 'text-solace-muted hover:text-solace-text'
                  }
                `}
              >
                {v.label}
                {v.key === 'incidents' && openIncidentCount > 0 && (
                  <span className="ml-1.5 inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full bg-red-500/20 text-red-400 text-[10px] font-mono font-bold">
                    {openIncidentCount}
                  </span>
                )}
              </button>
            ))}
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

          {/* Theme toggle */}
          <button
            onClick={toggleTheme}
            className="p-1.5 rounded-md hover:bg-solace-surface text-solace-muted hover:text-solace-bright transition-colors"
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {theme === 'dark' ? (
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                <circle cx="8" cy="8" r="3" />
                <path d="M8 1.5v1M8 13.5v1M1.5 8h1M13.5 8h1M3.4 3.4l.7.7M11.9 11.9l.7.7M3.4 12.6l.7-.7M11.9 4.1l.7-.7" />
              </svg>
            ) : (
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                <path d="M13.5 9.2A5.5 5.5 0 016.8 2.5 6 6 0 1013.5 9.2z" />
              </svg>
            )}
          </button>

          {/* User menu */}
          <div className="relative">
            <button
              onClick={() => setShowUserMenu(prev => !prev)}
              className="flex items-center gap-2 px-2 py-1 rounded-md hover:bg-solace-surface transition-colors"
            >
              <div className="w-6 h-6 rounded-full bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center text-white text-[10px] font-bold">
                {user.display_name.charAt(0).toUpperCase()}
              </div>
              <span className="text-xs text-solace-text">{user.display_name}</span>
              <span className={`px-1.5 py-0.5 text-[9px] font-mono font-bold uppercase rounded border ${ROLE_COLORS[user.role]}`}>
                {user.role}
              </span>
            </button>
            {showUserMenu && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setShowUserMenu(false)} />
                <div className="absolute right-0 top-full mt-1 z-50 w-48 bg-solace-surface border border-solace-border rounded-lg shadow-xl py-1">
                  <div className="px-3 py-2 border-b border-solace-border">
                    <div className="text-xs text-solace-bright font-medium">{user.display_name}</div>
                    <div className="text-[10px] text-solace-muted font-mono">@{user.username}</div>
                  </div>
                  <button
                    onClick={() => { setShowUserMenu(false); logout(); }}
                    className="w-full text-left px-3 py-2 text-xs text-red-400 hover:bg-red-500/10 transition-colors"
                  >
                    Sign Out
                  </button>
                </div>
              </>
            )}
          </div>
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

              {/* Tag filter chip */}
              {alertFilters.tag && (
                <>
                  <div className="w-px h-4 bg-solace-border mx-1" />
                  <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-teal-500/10 text-teal-400 text-[10px] font-mono border border-teal-500/20">
                    tag: {alertFilters.tag}
                    <button
                      onClick={() => setAlertFilters({ tag: undefined, page: 1 })}
                      className="ml-0.5 text-teal-400/50 hover:text-teal-400"
                    >
                      <svg width="8" height="8" viewBox="0 0 8 8" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <path d="M2 2l4 4M6 2l-4 4" />
                      </svg>
                    </button>
                  </span>
                </>
              )}
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

      {/* Bulk actions toolbar */}
      {view === 'alerts' && hasBulkSelection && !isViewer && (
        <div className="flex-shrink-0 flex items-center gap-3 px-5 py-2 border-b border-blue-500/20 bg-blue-500/5">
          <span className="text-xs font-mono text-blue-400">{selectedIds.size} selected</span>
          <button
            onClick={bulkAcknowledge}
            className="px-3 py-1 text-xs font-medium rounded bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 transition-colors"
          >
            Acknowledge
          </button>
          <button
            onClick={bulkResolve}
            className="px-3 py-1 text-xs font-medium rounded bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors"
          >
            Resolve
          </button>
          <button
            onClick={clearSelection}
            className="px-3 py-1 text-xs font-medium text-solace-muted hover:text-solace-text transition-colors"
          >
            Clear
          </button>
        </div>
      )}

      {/* ─── Stats Bar ──────────────────────────────────── */}
      {(view === 'alerts' || view === 'incidents') && <StatsBar stats={stats} />}

      {/* ─── Body ───────────────────────────────────────── */}
      {view === 'settings' ? (
        <SettingsView
          settings={settingsData}
          loading={settingsLoading}
          archiveDays={archiveDays}
          setArchiveDays={setArchiveDays}
          onArchive={handleArchive}
          archiveResult={archiveResult}
          isAdmin={isAdmin}
        />
      ) : view === 'silences' ? (
        <div className="flex-1 min-h-0">
          <SilenceList />
        </div>
      ) : view === 'channels' ? (
        <div className="flex-1 min-h-0">
          <NotificationChannelList />
        </div>
      ) : view === 'oncall' ? (
        <div className="flex-1 min-h-0">
          <OnCallView isAdmin={isAdmin} />
        </div>
      ) : view === 'users' && isAdmin ? (
        <div className="flex-1 min-h-0">
          <UserManagement />
        </div>
      ) : view === 'statistics' ? (
        <div className="flex-1 min-h-0">
          <StatisticsView stats={stats} />
        </div>
      ) : (
      <div className="flex-1 flex min-h-0">
        {/* List */}
        <div className="flex-1 flex flex-col min-h-0">
          {/* Column headers */}
          {view === 'alerts' ? (
            <div className="flex-shrink-0 flex items-center gap-3 px-4 py-2 border-b border-solace-border bg-solace-surface/20">
              {/* Select all checkbox */}
              {!isViewer && (
                <div className="flex-shrink-0" onClick={e => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={selectedIds.size > 0 && selectedIds.size === alerts.length}
                    onChange={() => selectedIds.size === alerts.length ? clearSelection() : selectAll()}
                    className="rounded border-solace-border bg-solace-bg text-blue-500 focus:ring-0 focus:ring-offset-0"
                  />
                </div>
              )}
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
            <div className="flex-shrink-0 flex items-center gap-3 px-4 py-2 border-b border-solace-border bg-solace-surface/20">
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
                      checked={selectedIds.has(alert.id)}
                      showCheckbox={!isViewer}
                      onSelect={selectAlert}
                      onAcknowledge={isViewer ? undefined : handleAlertAck}
                      onResolve={isViewer ? undefined : handleAlertResolve}
                      onToggleCheck={isViewer ? undefined : toggleSelect}
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
                      onAcknowledge={isViewer ? undefined : handleIncidentAck}
                      onResolve={isViewer ? undefined : handleIncidentResolve}
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
        {selectedAlert && (
          <div className="w-[400px] flex-shrink-0">
            <AlertDetail
              alert={selectedAlert}
              onAcknowledge={isViewer ? undefined : handleAlertAck}
              onResolve={isViewer ? undefined : handleAlertResolve}
              onClose={() => selectAlert(null)}
              onTagAdd={isViewer ? undefined : async (alertId, tag) => {
                const updated = await addTag(alertId, tag);
                return updated;
              }}
              onTagRemove={isViewer ? undefined : async (alertId, tag) => {
                const updated = await removeTag(alertId, tag);
                return updated;
              }}
              onTagClick={handleTagClick}
              onBackToIncident={view === 'incidents' && selectedIncident ? () => selectAlert(null) : undefined}
            />
          </div>
        )}
        {view === 'incidents' && selectedIncident && !selectedAlert && (
          <div className="w-[420px] flex-shrink-0">
            <IncidentDetail
              incident={selectedIncident}
              onAcknowledge={isViewer ? undefined : handleIncidentAck}
              onResolve={isViewer ? undefined : handleIncidentResolve}
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

function StatisticsView({ stats }: { stats: import('./lib/api').DashboardStats | null }) {
  if (!stats) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <span className="text-sm text-solace-muted">Loading statistics...</span>
      </div>
    );
  }

  const mtta = stats.mtta_seconds;
  const mttr = stats.mttr_seconds;

  const formatDuration = (seconds: number | null | undefined) => {
    if (!seconds) return '--';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    return `${(seconds / 3600).toFixed(1)}h`;
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 max-w-4xl mx-auto w-full space-y-6">
      <h1 className="text-lg font-semibold text-solace-bright">Statistics</h1>

      {/* Key metrics */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Active Alerts', value: stats.alerts.active, color: 'text-red-400' },
          { label: 'Open Incidents', value: stats.incidents.by_status.open || 0, color: 'text-orange-400' },
          { label: 'MTTA', value: formatDuration(mtta), color: 'text-blue-400' },
          { label: 'MTTR', value: formatDuration(mttr), color: 'text-emerald-400' },
        ].map(m => (
          <div key={m.label} className="bg-solace-surface rounded-lg border border-solace-border p-4">
            <div className="text-[10px] uppercase tracking-wider text-solace-muted mb-1">{m.label}</div>
            <div className={`text-2xl font-mono font-bold ${m.color}`}>{m.value}</div>
          </div>
        ))}
      </div>

      {/* Alerts by severity */}
      <section className="bg-solace-surface rounded-lg border border-solace-border p-5">
        <h2 className="text-sm font-semibold text-solace-bright mb-4">Alerts by Severity</h2>
        <div className="space-y-2">
          {(['critical', 'high', 'warning', 'low', 'info'] as const).map(sev => {
            const count = stats.alerts.by_severity[sev] || 0;
            const max = Math.max(...Object.values(stats.alerts.by_severity), 1);
            const pct = (count / max) * 100;
            const colors: Record<string, string> = {
              critical: 'bg-red-500',
              high: 'bg-orange-500',
              warning: 'bg-yellow-500',
              low: 'bg-blue-500',
              info: 'bg-gray-500',
            };
            return (
              <div key={sev} className="flex items-center gap-3">
                <span className="w-16 text-[10px] font-mono uppercase text-solace-muted">{sev}</span>
                <div className="flex-1 h-4 rounded bg-solace-bg overflow-hidden">
                  <div className={`h-full rounded ${colors[sev]} transition-all`} style={{ width: `${pct}%` }} />
                </div>
                <span className="w-10 text-right text-xs font-mono text-solace-bright">{count}</span>
              </div>
            );
          })}
        </div>
      </section>

      {/* Alerts by status */}
      <section className="bg-solace-surface rounded-lg border border-solace-border p-5">
        <h2 className="text-sm font-semibold text-solace-bright mb-4">Alerts by Status</h2>
        <div className="grid grid-cols-4 gap-4">
          {Object.entries(stats.alerts.by_status).map(([status, count]) => (
            <div key={status} className="text-center">
              <div className="text-xl font-mono font-bold text-solace-bright">{count}</div>
              <div className="text-[10px] uppercase tracking-wider text-solace-muted mt-0.5">{status}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Incidents by status */}
      <section className="bg-solace-surface rounded-lg border border-solace-border p-5">
        <h2 className="text-sm font-semibold text-solace-bright mb-4">Incidents by Status</h2>
        <div className="grid grid-cols-3 gap-4">
          {Object.entries(stats.incidents.by_status).map(([status, count]) => (
            <div key={status} className="text-center">
              <div className="text-xl font-mono font-bold text-solace-bright">{count}</div>
              <div className="text-[10px] uppercase tracking-wider text-solace-muted mt-0.5">{status}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function SettingsView({
  settings,
  loading,
  archiveDays,
  setArchiveDays,
  onArchive,
  archiveResult,
  isAdmin,
}: {
  settings: import('./lib/types').AppSettings | null;
  loading: boolean;
  archiveDays: number;
  setArchiveDays: (n: number) => void;
  onArchive: () => void;
  archiveResult: string | null;
  isAdmin: boolean;
}) {
  if (loading && !settings) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <span className="text-sm text-solace-muted">Loading settings...</span>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-6 max-w-3xl mx-auto w-full space-y-6">
      <h1 className="text-lg font-semibold text-solace-bright">Settings</h1>

      {/* General */}
      <section className="bg-solace-surface rounded-lg border border-solace-border p-5">
        <h2 className="text-sm font-semibold text-solace-bright mb-3">General</h2>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-[10px] uppercase tracking-wider text-solace-muted block mb-0.5">App Name</span>
            <span className="text-solace-bright font-mono">{settings?.app_name || '--'}</span>
          </div>
          <div>
            <span className="text-[10px] uppercase tracking-wider text-solace-muted block mb-0.5">Environment</span>
            <span className="text-solace-bright font-mono">{settings?.app_env || '--'}</span>
          </div>
        </div>
      </section>

      {/* Alert Processing */}
      <section className="bg-solace-surface rounded-lg border border-solace-border p-5">
        <h2 className="text-sm font-semibold text-solace-bright mb-3">Alert Processing</h2>
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <span className="text-[10px] uppercase tracking-wider text-solace-muted block mb-0.5">Dedup Window</span>
            <span className="text-solace-bright font-mono">{settings?.dedup_window_seconds ?? '--'}s</span>
          </div>
          <div>
            <span className="text-[10px] uppercase tracking-wider text-solace-muted block mb-0.5">Correlation Window</span>
            <span className="text-solace-bright font-mono">{settings?.correlation_window_seconds ?? '--'}s</span>
          </div>
          <div>
            <span className="text-[10px] uppercase tracking-wider text-solace-muted block mb-0.5">Notification Cooldown</span>
            <span className="text-solace-bright font-mono">{settings?.notification_cooldown_seconds ?? '--'}s</span>
          </div>
        </div>
      </section>

      {/* Alert Retention / Archive — admin only */}
      {isAdmin && (
        <section className="bg-solace-surface rounded-lg border border-solace-border p-5">
          <h2 className="text-sm font-semibold text-solace-bright mb-3">Alert Retention</h2>
          <p className="text-xs text-solace-muted mb-3">
            Archive resolved alerts older than a specified number of days. Archived alerts remain accessible under the "Archived" tab.
          </p>
          <div className="flex items-center gap-3">
            <label className="text-sm text-solace-text">Archive resolved alerts older than</label>
            <input
              type="number"
              min={1}
              value={archiveDays}
              onChange={e => setArchiveDays(Number(e.target.value) || 1)}
              className="w-20 px-2 py-1 text-sm font-mono bg-solace-bg border border-solace-border rounded text-solace-bright focus:outline-none focus:border-emerald-500/50"
            />
            <span className="text-sm text-solace-text">days</span>
            <button
              onClick={onArchive}
              className="px-3 py-1.5 text-xs font-medium rounded-md bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 transition-colors"
            >
              Archive Now
            </button>
            {archiveResult && (
              <span className="text-xs font-mono text-emerald-400">{archiveResult}</span>
            )}
          </div>
        </section>
      )}

      {/* Dashboard URL */}
      {settings?.solace_dashboard_url && (
        <section className="bg-solace-surface rounded-lg border border-solace-border p-5">
          <h2 className="text-sm font-semibold text-solace-bright mb-3">Dashboard URL</h2>
          <span className="text-sm text-solace-bright font-mono break-all">{settings.solace_dashboard_url}</span>
        </section>
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
