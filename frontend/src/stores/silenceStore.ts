import { create } from 'zustand';
import type { SilenceWindow } from '../lib/types';
import { api } from '../lib/api';

export interface SilenceFilters {
  state: string;
  page: number;
  pageSize: number;
}

interface SilenceState {
  windows: SilenceWindow[];
  total: number;
  loading: boolean;
  error: string | null;
  filters: SilenceFilters;

  fetchSilences: () => Promise<void>;
  setFilters: (partial: Partial<SilenceFilters>) => void;
  createSilence: (data: {
    name: string;
    matchers: Record<string, unknown>;
    starts_at: string;
    ends_at: string;
    created_by?: string;
    reason?: string;
  }) => Promise<void>;
  updateSilence: (id: string, data: Record<string, unknown>) => Promise<void>;
  deleteSilence: (id: string) => Promise<void>;
}

const DEFAULT_FILTERS: SilenceFilters = {
  state: 'all',
  page: 1,
  pageSize: 50,
};

export const useSilenceStore = create<SilenceState>((set, get) => ({
  windows: [],
  total: 0,
  loading: true,
  error: null,
  filters: { ...DEFAULT_FILTERS },

  fetchSilences: async () => {
    try {
      const f = get().filters;
      const data = await api.silences.list({
        state: f.state,
        page: f.page,
        page_size: f.pageSize,
      });
      set({ windows: data.windows, total: data.total, error: null, loading: false });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : 'Failed to fetch silences', loading: false });
    }
  },

  setFilters: (partial) => {
    set((state) => ({
      filters: { ...state.filters, ...partial },
      loading: true,
    }));
    get().fetchSilences();
  },

  createSilence: async (data) => {
    try {
      await api.silences.create(data);
      await get().fetchSilences();
    } catch (err) {
      set({ error: err instanceof Error ? err.message : 'Failed to create silence' });
    }
  },

  updateSilence: async (id, data) => {
    try {
      await api.silences.update(id, data);
      await get().fetchSilences();
    } catch (err) {
      set({ error: err instanceof Error ? err.message : 'Failed to update silence' });
    }
  },

  deleteSilence: async (id) => {
    try {
      await api.silences.delete(id);
      set((state) => ({
        windows: state.windows.filter((w) => w.id !== id),
      }));
    } catch (err) {
      set({ error: err instanceof Error ? err.message : 'Failed to delete silence' });
    }
  },
}));
