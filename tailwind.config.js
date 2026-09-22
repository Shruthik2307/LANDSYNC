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
        cyan: '#00F0FF',
        amber: '#FFB800',
        alert: '#FF4C4C',
        emerald: '#10B981',
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
