import { create } from 'zustand';
import { api } from '../lib/api';
import type { DashboardStats } from '../lib/api';

interface StatsState {
  stats: DashboardStats | null;
  loading: boolean;

  fetchStats: () => Promise<void>;
}

export const useStatsStore = create<StatsState>((set) => ({
  stats: null,
  loading: true,

  fetchStats: async () => {
    try {
      const data = await api.stats.get();
      set({ stats: data, loading: false });
    } catch {
      set({ loading: false });
    }
  },
}));
