import { create } from 'zustand';
import type { NotificationChannel, NotificationLog } from '../lib/types';
import { api } from '../lib/api';

interface NotificationState {
  channels: NotificationChannel[];
  logs: NotificationLog[];
  loading: boolean;
  logsLoading: boolean;
  error: string | null;

  fetchChannels: () => Promise<void>;
  fetchLogs: (channelId?: string) => Promise<void>;
  createChannel: (data: {
    name: string;
    channel_type: string;
    config: Record<string, unknown>;
    filters?: Record<string, unknown>;
  }) => Promise<void>;
  deleteChannel: (id: string) => Promise<void>;
  testChannel: (id: string) => Promise<{ status: string; message: string }>;
}

export const useNotificationStore = create<NotificationState>((set, get) => ({
  channels: [],
  logs: [],
  loading: true,
  logsLoading: false,
  error: null,

  fetchChannels: async () => {
    try {
      set({ loading: true });
      const data = await api.notifications.listChannels({ page_size: 100 });
      set({ channels: data.channels, error: null, loading: false });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : 'Failed to load channels', loading: false });
    }
  },

  fetchLogs: async (channelId) => {
    if (!channelId) {
      set({ logs: [] });
      return;
    }
    try {
      set({ logsLoading: true });
      const data = await api.notifications.listLogs({ channel_id: channelId, page_size: 50 });
      set({ logs: data.logs, logsLoading: false });
    } catch {
      set({ logsLoading: false });
    }
  },

  createChannel: async (data) => {
    await api.notifications.createChannel(data);
    await get().fetchChannels();
  },

  deleteChannel: async (id) => {
    await api.notifications.deleteChannel(id);
    await get().fetchChannels();
  },

  testChannel: async (id) => {
    return api.notifications.testChannel(id);
  },
}));
