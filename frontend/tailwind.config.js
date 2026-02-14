/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        mono: ['"JetBrains Mono"', '"Fira Code"', 'ui-monospace', 'monospace'],
        sans: ['"DM Sans"', 'system-ui', 'sans-serif'],
      },
      colors: {
        solace: {
          bg: 'var(--solace-bg)',
          surface: 'var(--solace-surface)',
          border: 'var(--solace-border)',
          muted: 'var(--solace-muted)',
          text: 'var(--solace-text)',
          bright: 'var(--solace-bright)',
        },
        severity: {
          critical: '#ef4444',
          high: '#f97316',
          warning: '#eab308',
          low: '#3b82f6',
          info: '#6b7280',
        },
      },
      keyframes: {
        'pulse-dot': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.3' },
        },
        'slide-in': {
          from: { opacity: '0', transform: 'translateY(-8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'pulse-dot': 'pulse-dot 2s ease-in-out infinite',
        'slide-in': 'slide-in 0.3s ease-out',
      },
    },
  },
  plugins: [],
}
