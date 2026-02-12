import { useState, useRef, useEffect } from 'react';

interface ExpandableTextProps {
  text: string;
  /** Max lines to show in collapsed state */
  maxLines?: number;
  className?: string;
}

export function ExpandableText({ text, maxLines = 2, className = '' }: ExpandableTextProps) {
  const [expanded, setExpanded] = useState(false);
  const [clamped, setClamped] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    // Check if text is actually overflowing
    setClamped(el.scrollHeight > el.clientHeight + 1);
  }, [text, maxLines]);

  return (
    <div className={className}>
      <div
        ref={ref}
        className={`text-sm text-solace-text leading-relaxed font-mono whitespace-pre-wrap break-words ${
          expanded ? '' : 'overflow-hidden'
        }`}
        style={expanded ? undefined : {
          display: '-webkit-box',
          WebkitLineClamp: maxLines,
          WebkitBoxOrient: 'vertical' as const,
        }}
      >
        {text}
      </div>
      {(clamped || expanded) && (
        <button
          onClick={() => setExpanded(e => !e)}
          className="mt-1 text-xs text-blue-400 hover:text-blue-300 transition-colors"
        >
          {expanded ? '▲ Show less' : '▼ Show more'}
        </button>
      )}
    </div>
  );
}
