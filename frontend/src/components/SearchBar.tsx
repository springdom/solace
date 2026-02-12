import { useState, useEffect, useRef } from 'react';

interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export function SearchBar({ value, onChange, placeholder = 'Search...' }: SearchBarProps) {
  const [local, setLocal] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  // Sync external changes
  useEffect(() => setLocal(value), [value]);

  // Debounce
  const handleChange = (v: string) => {
    setLocal(v);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => onChange(v), 250);
  };

  // Keyboard shortcut: "/" to focus
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === '/' && !['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement).tagName)) {
        e.preventDefault();
        inputRef.current?.focus();
      }
      if (e.key === 'Escape') {
        inputRef.current?.blur();
        if (local) handleChange('');
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [local]);

  return (
    <div className="relative">
      <svg
        width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2"
        className="absolute left-2.5 top-1/2 -translate-y-1/2 text-solace-muted pointer-events-none"
      >
        <circle cx="6.5" cy="6.5" r="4.5" />
        <path d="M10 10l4 4" />
      </svg>
      <input
        ref={inputRef}
        type="text"
        value={local}
        onChange={e => handleChange(e.target.value)}
        placeholder={placeholder}
        className="
          w-56 h-8 pl-8 pr-8 text-xs font-mono rounded-md
          bg-solace-surface border border-solace-border
          text-solace-bright placeholder-solace-muted
          focus:outline-none focus:border-solace-muted focus:ring-1 focus:ring-solace-muted/30
          transition-colors
        "
      />
      {local ? (
        <button
          onClick={() => handleChange('')}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-solace-muted hover:text-solace-text transition-colors"
        >
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 4l8 8M12 4l-8 8" />
          </svg>
        </button>
      ) : (
        <kbd className="absolute right-2 top-1/2 -translate-y-1/2 px-1 py-0.5 text-[9px] font-mono text-solace-muted border border-solace-border rounded">
          /
        </kbd>
      )}
    </div>
  );
}
