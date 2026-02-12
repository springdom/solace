import { useState, useEffect, useCallback, useRef } from 'react';
import type { SilenceWindow } from '../lib/types';
import { api } from '../lib/api';

const POLL_INTERVAL = 10000;

export interface UseSilencesOptions {
  state?: string;
  page?: number;
  pageSize?: number;
}

export function useSilences(opts: UseSilencesOptions = {}) {
  const [windows, setWindows] = useState<SilenceWindow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const optsRef = useRef(opts);
  optsRef.current = opts;

  const fetchSilences = useCallback(async () => {
    try {
      const o = optsRef.current;
      const data = await api.silences.list({
        state: o.state || 'all',
        page: o.page || 1,
        page_size: o.pageSize || 50,
      });
      setWindows(data.windows);
      setTotal(data.total);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch silences');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    fetchSilences();
  }, [opts.state, opts.page, opts.pageSize, fetchSilences]);

  useEffect(() => {
    const interval = setInterval(fetchSilences, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchSilences]);

  const createSilence = useCallback(async (data: {
    name: string;
    matchers: Record<string, unknown>;
    starts_at: string;
    ends_at: string;
    created_by?: string;
    reason?: string;
  }) => {
    try {
      await api.silences.create(data);
      await fetchSilences();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create silence');
    }
  }, [fetchSilences]);

  const deleteSilence = useCallback(async (id: string) => {
    try {
      await api.silences.delete(id);
      setWindows(prev => prev.filter(w => w.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete silence');
    }
  }, []);

  return { windows, total, loading, error, createSilence, deleteSilence, refetch: fetchSilences };
}
