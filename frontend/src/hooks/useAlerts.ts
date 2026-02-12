import { useAlertStore } from '../stores/alertStore';
import type { Alert } from '../lib/types';

export interface UseAlertsOptions {
  status?: string;
  severity?: string;
  search?: string;
  sortBy?: string;
  sortOrder?: string;
  page?: number;
  pageSize?: number;
}

export function useAlerts(_opts: UseAlertsOptions = {}) {
  const store = useAlertStore();

  return {
    alerts: store.alerts,
    total: store.total,
    loading: store.loading,
    error: store.error,
    acknowledge: store.acknowledge,
    resolve: store.resolve,
    addTag: store.addTag,
    removeTag: store.removeTag,
    refetch: store.fetchAlerts,
  };
}

// Re-export for convenience
export { useAlertStore } from '../stores/alertStore';
