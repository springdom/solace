import { create } from 'zustand';
import { useAlertStore } from './alertStore';
import { useIncidentStore } from './incidentStore';
import { useStatsStore } from './statsStore';

const RECONNECT_DELAY = 3000;
const PING_INTERVAL = 30000;
const ALERT_POLL = 30000;
const INCIDENT_POLL = 30000;
const STATS_POLL = 60000;

interface WSState {
  connected: boolean;
  _ws: WebSocket | null;
  _reconnectTimer: ReturnType<typeof setTimeout> | null;
  _pingTimer: ReturnType<typeof setInterval> | null;
  _pollTimers: ReturnType<typeof setInterval>[];

  init: () => void;
  cleanup: () => void;
}

export const useWSStore = create<WSState>((set, get) => ({
  connected: false,
  _ws: null,
  _reconnectTimer: null,
  _pingTimer: null,
  _pollTimers: [],

  init: () => {
    const state = get();
    // Prevent double-init
    if (state._ws) return;

    // Start fallback polling
    const pollTimers = [
      setInterval(() => useAlertStore.getState().fetchAlerts(), ALERT_POLL),
      setInterval(() => useIncidentStore.getState().fetchIncidents(), INCIDENT_POLL),
      setInterval(() => useStatsStore.getState().fetchStats(), STATS_POLL),
    ];
    set({ _pollTimers: pollTimers });

    // Initial data load
    useAlertStore.getState().fetchAlerts();
    useIncidentStore.getState().fetchIncidents();
    useStatsStore.getState().fetchStats();

    // Connect WebSocket
    const connect = () => {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      const token = localStorage.getItem('solace_token');
      const wsUrl = token
        ? `${proto}//${host}/api/v1/ws?token=${encodeURIComponent(token)}`
        : `${proto}//${host}/api/v1/ws`;
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        set({ connected: true });
        const pingTimer = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send('ping');
        }, PING_INTERVAL);
        set({ _pingTimer: pingTimer });
      };

      ws.onmessage = (e) => {
        try {
          const event = JSON.parse(e.data);
          if (event.type === 'pong') return;
          // Dispatch to relevant stores
          if (event.type.startsWith('alert.') || event.type.startsWith('incident.')) {
            useAlertStore.getState().fetchAlerts();
            useIncidentStore.getState().fetchIncidents();
            useStatsStore.getState().fetchStats();
          }
        } catch {
          // Ignore malformed messages
        }
      };

      ws.onclose = () => {
        set({ connected: false });
        const { _pingTimer } = get();
        if (_pingTimer) clearInterval(_pingTimer);
        const timer = setTimeout(connect, RECONNECT_DELAY);
        set({ _reconnectTimer: timer });
      };

      ws.onerror = () => ws.close();

      set({ _ws: ws });
    };

    connect();
  },

  cleanup: () => {
    const state = get();
    if (state._reconnectTimer) clearTimeout(state._reconnectTimer);
    if (state._pingTimer) clearInterval(state._pingTimer);
    state._pollTimers.forEach((t) => clearInterval(t));
    state._ws?.close();
    set({ _ws: null, _reconnectTimer: null, _pingTimer: null, _pollTimers: [], connected: false });
  },
}));
