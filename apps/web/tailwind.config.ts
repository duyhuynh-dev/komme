import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        canvas: "#f3efe6",
        ink: "#111827",
        accent: "#0f766e",
        accentSoft: "#d9f3f1",
        card: "#fffdf8",
        stroke: "#ddd6c4"
      },
      boxShadow: {
        float: "0 24px 48px rgba(17, 24, 39, 0.12)"
      },
      borderRadius: {
        xl2: "1.5rem"
      }
    }
  },
  plugins: []
};

export default config;

