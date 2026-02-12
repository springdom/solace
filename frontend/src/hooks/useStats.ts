import { useStatsStore } from '../stores/statsStore';

export function useStats() {
  const store = useStatsStore();
  return { stats: store.stats, loading: store.loading };
}

export { useStatsStore } from '../stores/statsStore';
