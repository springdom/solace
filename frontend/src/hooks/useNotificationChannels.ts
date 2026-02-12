import { useState, useEffect, useCallback } from 'react';
import type { NotificationChannel, NotificationLog } from '../lib/types';
import { api } from '../lib/api';

export function useNotificationChannels() {
  const [channels, setChannels] = useState<NotificationChannel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchChannels = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.notifications.listChannels({ page_size: 100 });
      setChannels(data.channels);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load channels');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchChannels();
  }, [fetchChannels]);

  const createChannel = useCallback(async (data: { name: string; channel_type: string; config: Record<string, unknown>; filters?: Record<string, unknown> }) => {
    await api.notifications.createChannel(data);
    await fetchChannels();
  }, [fetchChannels]);

  const deleteChannel = useCallback(async (id: string) => {
    await api.notifications.deleteChannel(id);
    await fetchChannels();
  }, [fetchChannels]);

  const testChannel = useCallback(async (id: string) => {
    return api.notifications.testChannel(id);
  }, []);

  return { channels, loading, error, createChannel, deleteChannel, testChannel, refetch: fetchChannels };
}

export function useNotificationLogs(channelId?: string) {
  const [logs, setLogs] = useState<NotificationLog[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchLogs = useCallback(async () => {
    if (!channelId) { setLogs([]); return; }
    try {
      setLoading(true);
      const data = await api.notifications.listLogs({ channel_id: channelId, page_size: 50 });
      setLogs(data.logs);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [channelId]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  return { logs, loading };
}
