/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './main/templates/**/*.html',
    './main/static/js/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        // Нова семантична система
        primary: 'rgb(var(--color-primary) / <alpha-value>)',
        success: 'rgb(var(--color-success) / <alpha-value>)',
        error: 'rgb(var(--color-error) / <alpha-value>)',
        background: 'rgb(var(--bg-main) / <alpha-value>)',
        surface: 'rgb(var(--bg-surface) / <alpha-value>)',
        mainText: 'rgb(var(--text-main) / <alpha-value>)',
        mutedText: 'rgb(var(--text-muted) / <alpha-value>)',
        border: 'rgb(var(--border-color) / <alpha-value>)',
        // Аліаси для шаблонів (адаптуються до теми через CSS-змінні)
        dark: 'rgb(var(--text-main) / <alpha-value>)',
        bodyText: 'rgb(var(--text-muted) / <alpha-value>)',
        // Статичні акцентні кольори (однакові в обох темах)
        accent: '#4CAF50',
        secondary: '#FF6B6B',
        neutral: '#A9A9A9',
      },
      boxShadow: {
        'glass': '0 8px 32px 0 rgba(0, 0, 0, 0.05)',
        'button': '0 4px 15px rgba(91, 132, 255, 0.3)',
        'button-hover': '0 6px 20px rgba(91, 132, 255, 0.4)',
      },
      backdropBlur: {
        'glass': '8px',
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', 'sans-serif'],
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        }
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-out forwards',
        'slide-up': 'slideUp 0.5s ease-out forwards',
      }
    },
  },
  plugins: [],
}
