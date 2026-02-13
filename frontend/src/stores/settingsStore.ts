import { create } from 'zustand';
import type { AppSettings } from '../lib/types';
import { api } from '../lib/api';

interface SettingsState {
  settings: AppSettings | null;
  loading: boolean;
  error: string | null;
  fetchSettings: () => Promise<void>;
}

export const useSettingsStore = create<SettingsState>((set) => ({
  settings: null,
  loading: true,
  error: null,

  fetchSettings: async () => {
    try {
      set({ loading: true });
      const data = await api.settings.get();
      set({ settings: data, error: null, loading: false });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : 'Failed to load settings', loading: false });
    }
  },
}));
