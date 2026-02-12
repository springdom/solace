import { useState, useEffect, useCallback } from 'react';
import { api } from '../lib/api';
import type { DashboardStats } from '../lib/api';

const POLL_INTERVAL = 10000;

export function useStats() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStats = useCallback(async () => {
    try {
      const data = await api.stats.get();
      setStats(data);
    } catch {
      // silently fail — stats are non-critical
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchStats]);

  return { stats, loading };
}
