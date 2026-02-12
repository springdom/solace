import { create } from 'zustand';
import type { Incident, IncidentDetail } from '../lib/types';
import { api } from '../lib/api';
import type { IncidentListParams } from '../lib/api';

export interface IncidentFilters {
  status?: string;
  search?: string;
  sortBy: string;
  sortOrder: 'asc' | 'desc';
  page: number;
  pageSize: number;
}

interface IncidentState {
  incidents: Incident[];
  total: number;
  loading: boolean;
  error: string | null;
  filters: IncidentFilters;
  selectedIncident: Incident | null;
  incidentDetail: IncidentDetail | null;
  detailLoading: boolean;

  // Actions
  fetchIncidents: () => Promise<void>;
  setFilters: (partial: Partial<IncidentFilters>) => void;
  resetFilters: () => void;
  selectIncident: (incident: Incident | null) => void;
  fetchDetail: (id: string) => Promise<void>;
  acknowledge: (id: string) => Promise<void>;
  resolve: (id: string) => Promise<void>;
}

const DEFAULT_FILTERS: IncidentFilters = {
  sortBy: 'started_at',
  sortOrder: 'desc',
  page: 1,
  pageSize: 25,
};

export const useIncidentStore = create<IncidentState>((set, get) => ({
  incidents: [],
  total: 0,
  loading: true,
  error: null,
  filters: { ...DEFAULT_FILTERS },
  selectedIncident: null,
  incidentDetail: null,
  detailLoading: false,

  fetchIncidents: async () => {
    try {
      const f = get().filters;
      const params: IncidentListParams = {
        status: f.status,
        q: f.search,
        sort_by: f.sortBy,
        sort_order: f.sortOrder,
        page: f.page,
        page_size: f.pageSize,
      };
      const data = await api.incidents.list(params);
      set({ incidents: data.incidents, total: data.total, error: null, loading: false });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : 'Failed to fetch incidents', loading: false });
    }
  },

  setFilters: (partial) => {
    set((state) => ({
      filters: { ...state.filters, ...partial },
      loading: true,
    }));
    get().fetchIncidents();
  },

  resetFilters: () => {
    set({ filters: { ...DEFAULT_FILTERS }, selectedIncident: null, loading: true });
    get().fetchIncidents();
  },

  selectIncident: (incident) => set({ selectedIncident: incident }),

  fetchDetail: async (id) => {
    set({ detailLoading: true });
    try {
      const detail = await api.incidents.get(id);
      set({ incidentDetail: detail, detailLoading: false });
    } catch {
      set({ incidentDetail: null, detailLoading: false });
    }
  },

  acknowledge: async (id) => {
    try {
      const updated = await api.incidents.acknowledge(id);
      set((state) => ({
        incidents: state.incidents.map((i) => (i.id === id ? { ...i, ...updated } : i)),
        selectedIncident: state.selectedIncident?.id === id
          ? { ...state.selectedIncident, status: 'acknowledged', acknowledged_at: new Date().toISOString() }
          : state.selectedIncident,
      }));
    } catch (err) {
      set({ error: err instanceof Error ? err.message : 'Failed to acknowledge' });
    }
  },

  resolve: async (id) => {
    try {
      const updated = await api.incidents.resolve(id);
      set((state) => ({
        incidents: state.incidents.map((i) => (i.id === id ? { ...i, ...updated } : i)),
        selectedIncident: state.selectedIncident?.id === id
          ? { ...state.selectedIncident, status: 'resolved', resolved_at: new Date().toISOString() }
          : state.selectedIncident,
      }));
    } catch (err) {
      set({ error: err instanceof Error ? err.message : 'Failed to resolve' });
    }
  },
}));
