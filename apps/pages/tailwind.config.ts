import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './index.html',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // Paper-editorial substrate — cream field, ink black
        bg:      '#ffffff',
        surface: '#f4f5f7',
        raised:  '#e9ebef',
        border:  '#c3c7cf',
        'border-bright': '#858a94',
        // Typography — warm near-black ink
        ink:   '#1a1410',
        body:  '#3f434a',
        muted: '#6b7079',
        // Accent — deep editorial navy (not bright blue, not green)
        accent: {
          DEFAULT: '#1c2d6b',
          dim:     '#0e1a42',
          glow:    'rgba(28,45,107,0.12)',
        },
        // Status — dark editorial tones on cream
        up:   '#1a5e33',
        down: '#8b1a1a',
        // Archive — muted rust
        archive: '#5a3a3a',
      },
      fontFamily: {
        sans:    ['Inter', 'system-ui', 'sans-serif'],
        mono:    ['JetBrains Mono', 'ui-monospace', 'monospace'],
        display: ['"Playfair Display"', 'Georgia', 'serif'],
        serif:   ['"Newsreader"', '"Playfair Display"', 'Georgia', 'serif'],
      },
      fontSize: {
        '2xs': ['0.65rem', { lineHeight: '1rem' }],
        '3xs': ['0.55rem', { lineHeight: '0.875rem' }],
      },
      borderColor: {
        DEFAULT: '#c3c7cf',
      },
      backgroundImage: {
        'hero-gradient':   'linear-gradient(to bottom, #f4f5f7, #ffffff)',
        'card-shine':      'linear-gradient(135deg, rgba(255,255,255,0.4) 0%, rgba(255,255,255,0) 60%)',
        'masthead-rule':   'linear-gradient(90deg, transparent, #c3c7cf 30%, #c3c7cf 70%, transparent)',
        'paper-grain':     'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'300\' height=\'300\'%3E%3Cfilter id=\'n\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.9\' numOctaves=\'4\' stitchTiles=\'stitch\'/%3E%3CfeColorMatrix type=\'saturate\' values=\'0\'/%3E%3C/filter%3E%3Crect width=\'300\' height=\'300\' filter=\'url(%23n)\' opacity=\'0.025\'/%3E%3C/svg%3E")',
      },
      boxShadow: {
        card:   '0 1px 3px rgba(0,0,0,0.08), 0 0 0 1px rgba(0,0,0,0.04)',
        glow:   '0 0 0 1px rgba(28,45,107,0.3), 0 0 12px rgba(28,45,107,0.1)',
        inset:  'inset 0 1px 0 rgba(255,255,255,0.6)',
      },
      letterSpacing: {
        masthead: '0.22em',
        label:    '0.12em',
      },
      animation: {
        ticker: 'ticker 52s linear infinite',
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
