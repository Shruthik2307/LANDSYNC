/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        void: '#030712',
        space: '#070D1D',
        surface: '#0B1528',
        surface2: '#101E38',
        surface3: '#182C50',
        midnight: '#0A0F1C',
        blueprint: '#16233D',
        ink: '#1F3355',
        paper: '#F1F5F9',
        // Brand accents (referenced as e.g. text-cyan / border-amber by name)
        // sit alongside the full DEFAULT Tailwind scales below — the scalar
        // override previously REPLACED the cyan/amber/emerald scales, so
        // every -300/-400/-500/-950 utility (incl. the primary CTA's
        // bg-cyan-400) was purged from production CSS and rendered invisible.
        cyan: {
          DEFAULT: '#00F0FF',
          200: '#a5f3fc',
          300: '#67e8f9',
          400: '#22d3ee',
          500: '#06b6d4',
          600: '#0891b2',
          900: '#164e63',
          950: '#083344',
        },
        amber: {
          DEFAULT: '#FFB800',
          200: '#fde68a',
          300: '#fcd34d',
          400: '#fbbf24',
          500: '#f59e0b',
          800: '#92400e',
          950: '#451a03',
        },
        emerald: {
          DEFAULT: '#10B981',
          200: '#a7f3d0',
          300: '#6ee7b7',
          400: '#34d399',
          500: '#10b981',
          600: '#059669',
          800: '#065f46',
          950: '#022c22',
        },
        alert: '#FF4C4C',
        blueTactical: '#3B82F6',
      },
      fontFamily: {
        sans: ['Space Grotesk', '-apple-system', 'sans-serif'],
        mono: ['IBM Plex Mono', 'monospace'],
      },
      boxShadow: {
        'hud': '0 16px 36px -8px rgba(0, 0, 0, 0.75), 0 0 0 1px rgba(0, 240, 255, 0.15) inset',
        'cyan-glow': '0 0 20px rgba(0, 240, 255, 0.25)',
        'amber-glow': '0 0 20px rgba(255, 184, 0, 0.25)',
        'alert-glow': '0 0 20px rgba(255, 76, 76, 0.25)',
      },
      borderColor: {
        'cyan-subtle': 'rgba(0, 240, 255, 0.14)',
        'cyan-glow': 'rgba(0, 240, 255, 0.35)',
      }
    },
  },
  plugins: [],
}
