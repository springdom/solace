import { useState, useRef, useEffect } from 'react';

export interface SortOption {
  value: string;
  label: string;
}

interface SortControlProps {
  options: SortOption[];
  sortBy: string;
  sortOrder: 'asc' | 'desc';
  onSort: (sortBy: string, sortOrder: 'asc' | 'desc') => void;
}

export function SortControl({ options, sortBy, sortOrder, onSort }: SortControlProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const current = options.find(o => o.value === sortBy);

  const toggleOrder = (e: React.MouseEvent) => {
    e.stopPropagation();
    onSort(sortBy, sortOrder === 'asc' ? 'desc' : 'asc');
  };

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="
          flex items-center gap-1.5 h-8 px-2.5 text-xs font-mono rounded-md
          bg-solace-surface border border-solace-border text-solace-text
          hover:border-solace-muted transition-colors
        "
      >
        <span className="text-solace-muted">Sort:</span>
        <span>{current?.label || sortBy}</span>
        <button
          onClick={toggleOrder}
          className="ml-0.5 p-0.5 rounded hover:bg-solace-border/50 transition-colors"
          title={sortOrder === 'asc' ? 'Ascending' : 'Descending'}
        >
          <svg width="10" height="10" viewBox="0 0 16 16" fill="currentColor"
            className={`transition-transform ${sortOrder === 'asc' ? 'rotate-180' : ''}`}
          >
            <path d="M8 2l5 6H3l5-6zM3 10h10l-5 6-5-6z" opacity="0.3" />
            <path d={sortOrder === 'desc' ? 'M3 10h10l-5 6-5-6z' : 'M8 2l5 6H3l5-6z'} opacity="1" />
          </svg>
        </button>
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 z-20 min-w-[160px] py-1 rounded-md bg-solace-surface border border-solace-border shadow-lg shadow-black/40">
          {options.map(opt => (
            <button
              key={opt.value}
              onClick={() => { onSort(opt.value, sortOrder); setOpen(false); }}
              className={`
                w-full px-3 py-1.5 text-left text-xs font-mono transition-colors
                ${opt.value === sortBy
                  ? 'text-solace-bright bg-solace-border/30'
                  : 'text-solace-text hover:bg-solace-border/20'
                }
              `}
            >
              {opt.label}
              {opt.value === sortBy && (
                <span className="ml-2 text-solace-muted">{sortOrder === 'asc' ? '↑' : '↓'}</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
