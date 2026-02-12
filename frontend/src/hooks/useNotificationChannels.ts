import { useEffect } from 'react';
import { useNotificationStore } from '../stores/notificationStore';

export function useNotificationChannels() {
  const store = useNotificationStore();

  // Fetch channels on mount
  useEffect(() => {
    store.fetchChannels();
  }, []);

  return {
    channels: store.channels,
    loading: store.loading,
    error: store.error,
    createChannel: store.createChannel,
    deleteChannel: store.deleteChannel,
    testChannel: store.testChannel,
    refetch: store.fetchChannels,
  };
}

export function useNotificationLogs(channelId?: string) {
  const store = useNotificationStore();

  useEffect(() => {
    store.fetchLogs(channelId);
  }, [channelId]);

  return {
    logs: store.logs,
    loading: store.logsLoading,
  };
}

export { useNotificationStore } from '../stores/notificationStore';
