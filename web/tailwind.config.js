import typography from "@tailwindcss/typography";

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#faf8f3",
        card: "#ffffff",
        ink: { DEFAULT: "#1c1b19", muted: "#6f6a62", faint: "#a39c90" },
        line: "#e9e4da",
        accent: { DEFAULT: "#15795f", dark: "#0f5a47", soft: "#e8f2ee" },
      },
      fontFamily: {
        display: ["Fraunces", "Georgia", "Noto Serif SC", "serif"],
        sans: [
          '"IBM Plex Sans"',
          '"PingFang SC"',
          '"Microsoft YaHei"',
          '"Noto Sans SC"',
          "system-ui",
          "sans-serif",
        ],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
      borderRadius: { xl: "0.9rem", "2xl": "1.25rem" },
      boxShadow: {
        soft: "0 1px 2px rgba(28,27,25,.04), 0 10px 30px -16px rgba(28,27,25,.14)",
        lift: "0 2px 8px rgba(28,27,25,.06), 0 28px 50px -24px rgba(28,27,25,.22)",
      },
      keyframes: {
        rise: {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "none" },
        },
        fade: { "0%": { opacity: "0" }, "100%": { opacity: "1" } },
      },
      animation: {
        rise: "rise .5s cubic-bezier(.2,.7,.2,1) both",
        fade: "fade .4s ease both",
      },
    },
  },
  plugins: [typography],
};
