interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}

export function Pagination({ page, pageSize, total, onPageChange }: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const from = Math.min((page - 1) * pageSize + 1, total);
  const to = Math.min(page * pageSize, total);

  if (total <= pageSize) return null;

  return (
    <div className="flex items-center justify-between px-5 py-2 border-t border-solace-border bg-solace-bg">
      <span className="text-xs text-solace-muted font-mono">
        {from}–{to} of {total}
      </span>

      <div className="flex items-center gap-1">
        <button
          disabled={page <= 1}
          onClick={() => onPageChange(1)}
          className="px-2 py-1 text-xs font-mono rounded-md text-solace-muted hover:text-solace-text hover:bg-solace-surface disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          title="First page"
        >
          ««
        </button>
        <button
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
          className="px-2 py-1 text-xs font-mono rounded-md text-solace-muted hover:text-solace-text hover:bg-solace-surface disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          title="Previous page"
        >
          «
        </button>

        <span className="px-3 py-1 text-xs font-mono text-solace-bright">
          {page} / {totalPages}
        </span>

        <button
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
          className="px-2 py-1 text-xs font-mono rounded-md text-solace-muted hover:text-solace-text hover:bg-solace-surface disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          title="Next page"
        >
          »
        </button>
        <button
          disabled={page >= totalPages}
          onClick={() => onPageChange(totalPages)}
          className="px-2 py-1 text-xs font-mono rounded-md text-solace-muted hover:text-solace-text hover:bg-solace-surface disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          title="Last page"
        >
          »»
        </button>
      </div>
    </div>
  );
}
