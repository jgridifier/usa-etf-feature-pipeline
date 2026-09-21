import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './index.html',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // Dark editorial palette — warmer near-black
        bg:      '#0d0e0f',
        surface: '#141516',
        raised:  '#1c1e21',
        border:  '#2a2d33',
        'border-bright': '#3c4050',
        // Typography — warm white ink
        ink:   '#f2f0eb',
        body:  '#8a8e9a',
        muted: '#525663',
        // Accent — restrained editorial blue
        accent: {
          DEFAULT: '#4f7ef8',
          dim:     '#2a4fad',
          glow:    'rgba(79,126,248,0.15)',
        },
        // Status
        up:   '#22d68e',
        down: '#f06060',
        // Archive — muted rust, never promoted
        archive: '#5a3a3a',
      },
      fontFamily: {
        sans:    ['Inter', 'system-ui', 'sans-serif'],
        mono:    ['JetBrains Mono', 'ui-monospace', 'monospace'],
        display: ['"Playfair Display"', 'Georgia', 'serif'],
        serif:   ['"Playfair Display"', 'Georgia', 'serif'],
      },
      fontSize: {
        '2xs': ['0.65rem', { lineHeight: '1rem' }],
        '3xs': ['0.55rem', { lineHeight: '0.875rem' }],
      },
      borderColor: {
        DEFAULT: '#2a2d33',
      },
      backgroundImage: {
        'hero-gradient':   'linear-gradient(to bottom, #111316, #0d0e0f)',
        'card-shine':      'linear-gradient(135deg, rgba(255,255,255,0.025) 0%, rgba(255,255,255,0) 60%)',
        'masthead-rule':   'linear-gradient(90deg, transparent, #3c4050 30%, #3c4050 70%, transparent)',
      },
      boxShadow: {
        card:   '0 1px 3px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.04)',
        glow:   '0 0 0 1px rgba(79,126,248,0.4), 0 0 12px rgba(79,126,248,0.15)',
        inset:  'inset 0 1px 0 rgba(255,255,255,0.05)',
      },
      letterSpacing: {
        masthead: '0.22em',
        label:    '0.12em',
      },
      animation: {
        ticker: 'ticker 40s linear infinite',
      },
      keyframes: {
        ticker: {
          '0%':   { transform: 'translateX(0)' },
          '100%': { transform: 'translateX(-50%)' },
        },
        pulse: {
          '0%, 100%': { opacity: '1' },
          '50%':      { opacity: '0.4' },
        },
      },
    },
  },
  plugins: [],
}

export default config
