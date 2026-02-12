interface ColumnHeaderProps {
  label: string;
  sortKey: string;
  currentSort: string;
  currentOrder: string;
  onSort: (key: string) => void;
  className?: string;
}

export function ColumnHeader({ label, sortKey, currentSort, currentOrder, onSort, className = '' }: ColumnHeaderProps) {
  const isActive = currentSort === sortKey;

  return (
    <button
      onClick={() => onSort(sortKey)}
      className={`
        flex items-center gap-1 text-[10px] uppercase tracking-wider font-semibold transition-colors
        ${isActive ? 'text-blue-400' : 'text-solace-muted hover:text-solace-text'}
        ${className}
      `}
    >
      {label}
      <span className="inline-flex flex-col leading-none -space-y-px">
        <svg width="8" height="5" viewBox="0 0 8 5" fill="none">
          <path
            d="M4 0L7.5 4.5H0.5L4 0Z"
            fill={isActive && currentOrder === 'asc' ? 'currentColor' : 'rgba(128,128,128,0.25)'}
          />
        </svg>
        <svg width="8" height="5" viewBox="0 0 8 5" fill="none">
          <path
            d="M4 5L0.5 0.5H7.5L4 5Z"
            fill={isActive && currentOrder === 'desc' ? 'currentColor' : 'rgba(128,128,128,0.25)'}
          />
        </svg>
      </span>
    </button>
  );
}
