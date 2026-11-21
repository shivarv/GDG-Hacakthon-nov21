/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eef4ff',
          100: '#dbe6fe',
          500: '#3b6cf6',
          600: '#2753e0',
          700: '#1f42b5',
        },
      },
    },
  },
  plugins: [],
};
