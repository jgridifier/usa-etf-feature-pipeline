import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './index.html',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // Dark editorial palette
        bg:      '#0a0c10',       // deep page background
        surface: '#121419',       // card / panel surface
        raised:  '#1a1d26',       // slightly elevated surface
        border:  '#252836',       // default border
        'border-bright': '#383d52', // hover / focus border
        // Typography
        ink:   '#f0f1f5',         // primary text / headings
        body:  '#7e8699',         // secondary / body text
        muted: '#4a5166',         // de-emphasised / placeholders
        // Accent – restrained editorial blue
        accent: {
          DEFAULT: '#4f7ef8',
          dim:     '#2a4fad',
          glow:    'rgba(79,126,248,0.15)',
        },
        // Status
        up:   '#22d68e',
        down: '#f06060',
        // Archive – visually muted, never promoted
        archive: '#5a3a3a',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
        display: ['Inter', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        '2xs': ['0.65rem', { lineHeight: '1rem' }],
      },
      borderColor: {
        DEFAULT: '#252836',
      },
      backgroundImage: {
        'hero-gradient': 'linear-gradient(to bottom, #10131c, #0a0c10)',
        'card-shine':    'linear-gradient(135deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0) 60%)',
      },
      boxShadow: {
        card: '0 1px 2px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.04)',
        glow: '0 0 0 1px rgba(79,126,248,0.4), 0 0 12px rgba(79,126,248,0.15)',
      },
      keyframes: {
        pulse: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.4' },
        },
      },
    },
  },
  plugins: [],
}

export default config
