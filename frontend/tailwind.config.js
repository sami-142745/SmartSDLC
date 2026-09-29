/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        /* Base canvas. `surface-0` is the canonical #09090B app background. */
        surface: {
          0: '#09090B',
          1: '#0E0E13',
          2: '#131318',
          3: '#1A1A21',
          4: '#23232C',
          5: '#2E2E3A',
          6: '#3B3B49',
        },
        /* Violet -> cyan brand ramp. */
        accent: {
          blue: '#3B82F6',
          indigo: '#6366F1',
          violet: '#8B5CF6',
          purple: '#A855F7',
          cyan: '#22D3EE',
          teal: '#2DD4BF',
          lavender: '#C4B5FD',
        },
        /* Semantic surfaces tuned for dark UI legibility. */
        ink: {
          DEFAULT: '#FAFAFA',
          muted: '#A1A1AA',
          subtle: '#71717A',
          faint: '#52525B',
        },
      },
      fontFamily: {
        sans: [
          'Inter',
          'ui-sans-serif',
          'system-ui',
          '-apple-system',
          'Segoe UI',
          'Roboto',
          'Helvetica',
          'Arial',
          'sans-serif',
        ],
        mono: [
          'JetBrains Mono',
          'ui-monospace',
          'SFMono-Regular',
          'Menlo',
          'Consolas',
          'monospace',
        ],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
        display: ['3rem', { lineHeight: '1.06', letterSpacing: '-0.032em', fontWeight: '600' }],
        headline: ['2rem', { lineHeight: '1.15', letterSpacing: '-0.028em', fontWeight: '600' }],
      },
      boxShadow: {
        subtle: '0 1px 2px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.05)',
        elevated: '0 2px 8px rgba(0,0,0,0.45), 0 0 0 1px rgba(255,255,255,0.06)',
        lifted: '0 12px 32px -12px rgba(0,0,0,0.7), 0 0 0 1px rgba(255,255,255,0.08)',
        'glass-sm': '0 1px 2px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.05)',
        'glass-md': '0 8px 24px -8px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.06), 0 0 0 1px rgba(255,255,255,0.07)',
        'glass-lg': '0 24px 60px -20px rgba(0,0,0,0.75), inset 0 1px 0 rgba(255,255,255,0.07), 0 0 0 1px rgba(255,255,255,0.09)',
        'glow-sm': '0 0 0 1px rgba(139,92,246,0.28), 0 0 16px -6px rgba(139,92,246,0.4)',
        'glow-md': '0 0 0 1px rgba(139,92,246,0.36), 0 0 28px -8px rgba(139,92,246,0.55)',
        'glow-lg': '0 0 0 1px rgba(139,92,246,0.45), 0 0 48px -10px rgba(139,92,246,0.7)',
        'glow-cyan': '0 0 0 1px rgba(34,211,238,0.32), 0 0 24px -8px rgba(34,211,238,0.5)',
        focus: '0 0 0 2px #09090B, 0 0 0 4px rgba(139,92,246,0.65)',
      },
      backgroundImage: {
        'brand-gradient': 'linear-gradient(135deg, #8B5CF6 0%, #6366F1 50%, #22D3EE 100%)',
        'brand-gradient-soft':
          'linear-gradient(135deg, rgba(139,92,246,0.16) 0%, rgba(99,102,241,0.14) 50%, rgba(34,211,238,0.12) 100%)',
        'glass-gradient': 'linear-gradient(180deg, rgba(255,255,255,0.035) 0%, rgba(255,255,255,0) 100%)',
        'glass-gradient-strong':
          'linear-gradient(180deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.012) 100%)',
        'grid-fine':
          'linear-gradient(to right, rgba(255,255,255,0.028) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.028) 1px, transparent 1px)',
        'hairline': 'linear-gradient(90deg, transparent, rgba(255,255,255,0.12), transparent)',
      },
      transitionTimingFunction: {
        swift: 'cubic-bezier(0.16, 1, 0.3, 1)',
      },
      keyframes: {
        'fade-in': { from: { opacity: '0' }, to: { opacity: '1' } },
        'slide-up': {
          from: { opacity: '0', transform: 'translateY(10px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'scale-in': {
          from: { opacity: '0', transform: 'scale(0.97)' },
          to: { opacity: '1', transform: 'scale(1)' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
        'pulse-ring': {
          '0%': { opacity: '0.7', transform: 'scale(0.85)' },
          '70%': { opacity: '0', transform: 'scale(1.6)' },
          '100%': { opacity: '0', transform: 'scale(1.6)' },
        },
        'spin-slow': { to: { transform: 'rotate(360deg)' } },
        'dash-flow': { to: { strokeDashoffset: '-16' } },
      },
      animation: {
        'fade-in': 'fade-in 0.4s cubic-bezier(0.16,1,0.3,1) both',
        'slide-up': 'slide-up 0.45s cubic-bezier(0.16,1,0.3,1) both',
        'scale-in': 'scale-in 0.3s cubic-bezier(0.16,1,0.3,1) both',
        shimmer: 'shimmer 1.8s infinite',
        'pulse-ring': 'pulse-ring 2.4s cubic-bezier(0.16,1,0.3,1) infinite',
        'spin-slow': 'spin-slow 1s linear infinite',
        'dash-flow': 'dash-flow 0.6s linear infinite',
      },
    },
  },
  plugins: [],
};
