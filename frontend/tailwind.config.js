/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0D1218",
          900: "#12181F",
          800: "#1B232C",
          700: "#222C36",
          600: "#2C3742",
          500: "#3C4A57",
        },
        mist: {
          100: "#E8EDF2",
          300: "#B7C2CC",
          500: "#8B98A6",
        },
        brand: {
          DEFAULT: "#5B8DEF",
          dim: "#3F6BC4",
        },
        gold: {
          DEFAULT: "#D6A756",
          dim: "#B8893D",
        },
        good: {
          DEFAULT: "#3FB88F",
          dim: "#2C8F6E",
        },
        bad: {
          DEFAULT: "#E2685C",
          dim: "#B84E44",
        },
      },
      fontFamily: {
        sans: ["IBM Plex Sans", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "monospace"],
      },
      borderRadius: {
        sm: "4px",
        DEFAULT: "6px",
      },
    },
  },
  plugins: [],
}
