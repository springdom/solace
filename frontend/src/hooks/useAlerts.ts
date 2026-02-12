import { useState, useEffect, useCallback, useRef } from 'react';
import type { Alert } from '../lib/types';
import { api } from '../lib/api';
import type { AlertListParams } from '../lib/api';

const POLL_INTERVAL = 5000;

export interface UseAlertsOptions {
  status?: string;
  severity?: string;
  search?: string;
  sortBy?: string;
  sortOrder?: string;
  page?: number;
  pageSize?: number;
}

export function useAlerts(opts: UseAlertsOptions = {}) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const optsRef = useRef(opts);
  optsRef.current = opts;

  const fetchAlerts = useCallback(async () => {
    try {
      const o = optsRef.current;
      const params: AlertListParams = {
        status: o.status,
        severity: o.severity,
        q: o.search,
        sort_by: o.sortBy || 'created_at',
        sort_order: o.sortOrder || 'desc',
        page: o.page || 1,
        page_size: o.pageSize || 25,
      };
      const data = await api.alerts.list(params);
      setAlerts(data.alerts);
      setTotal(data.total);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch alerts');
    } finally {
      setLoading(false);
    }
  }, []);

  // Refetch on option changes
  useEffect(() => {
    setLoading(true);
    fetchAlerts();
  }, [opts.status, opts.severity, opts.search, opts.sortBy, opts.sortOrder, opts.page, opts.pageSize, fetchAlerts]);

  // Polling
  useEffect(() => {
    const interval = setInterval(fetchAlerts, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchAlerts]);

  const acknowledge = useCallback(async (id: string) => {
    try {
      const updated = await api.alerts.acknowledge(id);
      setAlerts(prev => prev.map(a => a.id === id ? updated : a));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to acknowledge');
    }
  }, []);

  const resolve = useCallback(async (id: string) => {
    try {
      const updated = await api.alerts.resolve(id);
      setAlerts(prev => prev.map(a => a.id === id ? updated : a));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resolve');
    }
  }, []);

  return { alerts, total, loading, error, acknowledge, resolve, refetch: fetchAlerts };
}
