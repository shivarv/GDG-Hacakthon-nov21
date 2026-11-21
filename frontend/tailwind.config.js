import defaultTheme from 'tailwindcss/defaultTheme';

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', ...defaultTheme.fontFamily.sans],
      },
      colors: {
        brand: {
          50: '#eef2ff',
          100: '#e0e7ff',
          200: '#c7d2fe',
          500: '#6366f1',
          600: '#4f46e5',
          700: '#4338ca',
          900: '#1e1b4b',
        },
      },
      // About 1px larger than Tailwind's defaults for easier reading.
      fontSize: {
        xs: ['0.8125rem', { lineHeight: '1.25rem' }], // 13px
        sm: ['0.9375rem', { lineHeight: '1.5rem' }], // 15px
        base: ['1.0625rem', { lineHeight: '1.75rem' }], // 17px
        lg: ['1.1875rem', { lineHeight: '1.875rem' }], // 19px
      },
      boxShadow: {
        card: '0 1px 2px 0 rgb(15 23 42 / 0.04), 0 2px 6px -1px rgb(15 23 42 / 0.06)',
        'card-hover': '0 4px 12px -2px rgb(15 23 42 / 0.10), 0 2px 4px -2px rgb(15 23 42 / 0.06)',
      },
    },
  },
  plugins: [],
};
