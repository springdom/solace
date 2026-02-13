import { useEffect } from 'react';
import { useSilenceStore } from '../stores/silenceStore';

export interface UseSilencesOptions {
  state?: string;
  page?: number;
  pageSize?: number;
}

export function useSilences(opts: UseSilencesOptions = {}) {
  const store = useSilenceStore();

  // Sync filter options from component to store
  useEffect(() => {
    store.setFilters({
      state: opts.state || 'all',
      page: opts.page || 1,
      pageSize: opts.pageSize || 50,
    });
  }, [opts.state, opts.page, opts.pageSize]);

  return {
    windows: store.windows,
    total: store.total,
    loading: store.loading,
    error: store.error,
    createSilence: store.createSilence,
    updateSilence: store.updateSilence,
    deleteSilence: store.deleteSilence,
    refetch: store.fetchSilences,
  };
}

export { useSilenceStore } from '../stores/silenceStore';
