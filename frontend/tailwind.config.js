/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        sidebar: '#111827',
        accent: '#10a37f',
        'accent-hover': '#0d8f6f',
        surface: '#1f2937',
        'surface-2': '#374151',
        border: '#374151',
        'text-primary': '#f1f5f9',
        'text-secondary': '#94a3b8',
        'text-muted': '#64748b',
      },
    },
  },
  plugins: [],
};
