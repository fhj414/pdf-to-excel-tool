import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#111827",
        slate: "#5b6472",
        line: "#d9e1ea",
        panel: "#f7f9fc",
        accent: "#0f766e",
        warn: "#f59e0b",
        danger: "#dc2626"
      },
      boxShadow: {
        card: "0 20px 45px rgba(15, 23, 42, 0.08)"
      },
      backgroundImage: {
        grid: "linear-gradient(to right, rgba(15, 23, 42, 0.04) 1px, transparent 1px), linear-gradient(to bottom, rgba(15, 23, 42, 0.04) 1px, transparent 1px)"
      }
    }
  },
  plugins: []
};

export default config;

