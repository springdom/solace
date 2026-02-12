import { useState, useEffect, useCallback, useRef } from 'react';
import type { Incident, IncidentDetail } from '../lib/types';
import { api } from '../lib/api';
import type { IncidentListParams } from '../lib/api';

const POLL_INTERVAL = 5000;

export interface UseIncidentsOptions {
  status?: string;
  search?: string;
  sortBy?: string;
  sortOrder?: string;
  page?: number;
  pageSize?: number;
}

export function useIncidents(opts: UseIncidentsOptions = {}) {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const optsRef = useRef(opts);
  optsRef.current = opts;

  const fetchIncidents = useCallback(async () => {
    try {
      const o = optsRef.current;
      const params: IncidentListParams = {
        status: o.status,
        q: o.search,
        sort_by: o.sortBy || 'started_at',
        sort_order: o.sortOrder || 'desc',
        page: o.page || 1,
        page_size: o.pageSize || 25,
      };
      const data = await api.incidents.list(params);
      setIncidents(data.incidents);
      setTotal(data.total);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch incidents');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    fetchIncidents();
  }, [opts.status, opts.search, opts.sortBy, opts.sortOrder, opts.page, opts.pageSize, fetchIncidents]);

  useEffect(() => {
    const interval = setInterval(fetchIncidents, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchIncidents]);

  const acknowledge = useCallback(async (id: string) => {
    try {
      const updated = await api.incidents.acknowledge(id);
      setIncidents(prev => prev.map(i => i.id === id ? { ...i, ...updated } : i));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to acknowledge');
    }
  }, []);

  const resolve = useCallback(async (id: string) => {
    try {
      const updated = await api.incidents.resolve(id);
      setIncidents(prev => prev.map(i => i.id === id ? { ...i, ...updated } : i));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resolve');
    }
  }, []);

  return { incidents, total, loading, error, acknowledge, resolve, refetch: fetchIncidents };
}

export function useIncidentDetail(incidentId: string | null) {
  const [incident, setIncident] = useState<IncidentDetail | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!incidentId) { setIncident(null); return; }
    setLoading(true);
    api.incidents.get(incidentId)
      .then(setIncident)
      .catch(() => setIncident(null))
      .finally(() => setLoading(false));
  }, [incidentId]);

  return { incident, loading };
}
