/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["DM Sans", "system-ui", "sans-serif"],
        display: ["Outfit", "system-ui", "sans-serif"],
      },
      colors: {
        night: {
          950: "#070a0f",
          900: "#0c1118",
          850: "#121a24",
          800: "#1a2433",
        },
        mint: {
          400: "#5eead4",
          500: "#2dd4bf",
          600: "#14b8a6",
        },
      },
      backgroundImage: {
        grid: `linear-gradient(to right, rgba(45,212,191,0.06) 1px, transparent 1px),
               linear-gradient(to bottom, rgba(45,212,191,0.06) 1px, transparent 1px)`,
      },
    },
  },
  plugins: [],
};
