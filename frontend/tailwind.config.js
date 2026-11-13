/** @type {import('tailwindcss').Config} */
// Colors are CSS variables holding space-separated RGB triplets (see src/index.css),
// so Tailwind opacity modifiers like bg-bg/50 keep working.
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg: "rgb(var(--color-bg) / <alpha-value>)",
        fg: "rgb(var(--color-fg) / <alpha-value>)",
        muted: "rgb(var(--color-muted) / <alpha-value>)",
        accent: "rgb(var(--color-accent) / <alpha-value>)",
      },
    },
  },
  plugins: [],
};
