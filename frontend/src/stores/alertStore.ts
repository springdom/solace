import { create } from 'zustand';
import type { Alert } from '../lib/types';
import { api } from '../lib/api';
import type { AlertListParams } from '../lib/api';

export interface AlertFilters {
  status?: string;
  severity?: string;
  tag?: string;
  search?: string;
  sortBy: string;
  sortOrder: 'asc' | 'desc';
  page: number;
  pageSize: number;
}

interface AlertState {
  alerts: Alert[];
  total: number;
  loading: boolean;
  error: string | null;
  filters: AlertFilters;
  selectedAlert: Alert | null;

  // Bulk selection
  selectedIds: Set<string>;

  // Actions
  fetchAlerts: () => Promise<void>;
  setFilters: (partial: Partial<AlertFilters>) => void;
  resetFilters: () => void;
  selectAlert: (alert: Alert | null) => void;
  acknowledge: (id: string) => Promise<void>;
  resolve: (id: string) => Promise<void>;
  addTag: (alertId: string, tag: string) => Promise<Alert | undefined>;
  removeTag: (alertId: string, tag: string) => Promise<Alert | undefined>;

  // Bulk actions
  toggleSelect: (id: string) => void;
  selectAll: () => void;
  clearSelection: () => void;
  bulkAcknowledge: () => Promise<void>;
  bulkResolve: () => Promise<void>;
}

const DEFAULT_FILTERS: AlertFilters = {
  sortBy: 'created_at',
  sortOrder: 'desc',
  page: 1,
  pageSize: 25,
};

export const useAlertStore = create<AlertState>((set, get) => ({
  alerts: [],
  total: 0,
  loading: true,
  error: null,
  filters: { ...DEFAULT_FILTERS },
  selectedAlert: null,
  selectedIds: new Set(),

  fetchAlerts: async () => {
    try {
      const f = get().filters;
      const params: AlertListParams = {
        status: f.status,
        severity: f.severity,
        tag: f.tag,
        q: f.search,
        sort_by: f.sortBy,
        sort_order: f.sortOrder,
        page: f.page,
        page_size: f.pageSize,
      };
      const data = await api.alerts.list(params);
      set({ alerts: data.alerts, total: data.total, error: null, loading: false });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : 'Failed to fetch alerts', loading: false });
    }
  },

  setFilters: (partial) => {
    set((state) => ({
      filters: { ...state.filters, ...partial },
      loading: true,
    }));
    get().fetchAlerts();
  },

  resetFilters: () => {
    set({ filters: { ...DEFAULT_FILTERS }, selectedAlert: null, selectedIds: new Set(), loading: true });
    get().fetchAlerts();
  },

  selectAlert: (alert) => set({ selectedAlert: alert }),

  acknowledge: async (id) => {
    try {
      const updated = await api.alerts.acknowledge(id);
      set((state) => ({
        alerts: state.alerts.map((a) => (a.id === id ? updated : a)),
        selectedAlert: state.selectedAlert?.id === id
          ? { ...state.selectedAlert, status: 'acknowledged', acknowledged_at: new Date().toISOString() }
          : state.selectedAlert,
      }));
    } catch (err) {
      set({ error: err instanceof Error ? err.message : 'Failed to acknowledge' });
    }
  },

  resolve: async (id) => {
    try {
      const updated = await api.alerts.resolve(id);
      set((state) => ({
        alerts: state.alerts.map((a) => (a.id === id ? updated : a)),
        selectedAlert: state.selectedAlert?.id === id
          ? { ...state.selectedAlert, status: 'resolved', resolved_at: new Date().toISOString() }
          : state.selectedAlert,
      }));
    } catch (err) {
      set({ error: err instanceof Error ? err.message : 'Failed to resolve' });
    }
  },

  addTag: async (alertId, tag) => {
    try {
      const updated = await api.alerts.addTag(alertId, tag);
      set((state) => ({
        alerts: state.alerts.map((a) => (a.id === alertId ? updated : a)),
        selectedAlert: state.selectedAlert?.id === alertId ? updated : state.selectedAlert,
      }));
      return updated;
    } catch (err) {
      set({ error: err instanceof Error ? err.message : 'Failed to add tag' });
    }
  },

  removeTag: async (alertId, tag) => {
    try {
      const updated = await api.alerts.removeTag(alertId, tag);
      set((state) => ({
        alerts: state.alerts.map((a) => (a.id === alertId ? updated : a)),
        selectedAlert: state.selectedAlert?.id === alertId ? updated : state.selectedAlert,
      }));
      return updated;
    } catch (err) {
      set({ error: err instanceof Error ? err.message : 'Failed to remove tag' });
    }
  },

  toggleSelect: (id) => {
    set((state) => {
      const next = new Set(state.selectedIds);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return { selectedIds: next };
    });
  },

  selectAll: () => {
    set((state) => ({
      selectedIds: new Set(state.alerts.map(a => a.id)),
    }));
  },

  clearSelection: () => set({ selectedIds: new Set() }),

  bulkAcknowledge: async () => {
    const ids = Array.from(get().selectedIds);
    if (ids.length === 0) return;
    try {
      await api.alerts.bulkAcknowledge(ids);
      set({ selectedIds: new Set() });
      await get().fetchAlerts();
    } catch (err) {
      set({ error: err instanceof Error ? err.message : 'Bulk acknowledge failed' });
    }
  },

  bulkResolve: async () => {
    const ids = Array.from(get().selectedIds);
    if (ids.length === 0) return;
    try {
      await api.alerts.bulkResolve(ids);
      set({ selectedIds: new Set() });
      await get().fetchAlerts();
    } catch (err) {
      set({ error: err instanceof Error ? err.message : 'Bulk resolve failed' });
    }
  },
}));
