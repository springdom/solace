import { useIncidentStore } from '../stores/incidentStore';
import type { IncidentDetail } from '../lib/types';

export interface UseIncidentsOptions {
  status?: string;
  search?: string;
  sortBy?: string;
  sortOrder?: string;
  page?: number;
  pageSize?: number;
}

export function useIncidents(_opts: UseIncidentsOptions = {}) {
  const store = useIncidentStore();

  return {
    incidents: store.incidents,
    total: store.total,
    loading: store.loading,
    error: store.error,
    acknowledge: store.acknowledge,
    resolve: store.resolve,
    refetch: store.fetchIncidents,
  };
}

export function useIncidentDetail(incidentId: string | null) {
  const store = useIncidentStore();

  // Fetch detail when requested
  if (incidentId && store.incidentDetail?.id !== incidentId) {
    store.fetchDetail(incidentId);
  }

  return {
    incident: incidentId ? store.incidentDetail : null,
    loading: store.detailLoading,
  };
}

export { useIncidentStore } from '../stores/incidentStore';
