import type { Config } from "tailwindcss";

/**
 * Design tokens from design-spec-buyer-portal-demo §2. The portal renders two
 * surfaces (Buyer / Hospital) on the same Tailwind config but with different
 * primary palettes — this is achieved through CSS variables + two utility
 * classes (``surface-buyer`` / ``surface-hospital``). The Tailwind "primary"
 * alias resolves the CSS variable at runtime, so the same component can live
 * on either surface.
 */
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "var(--rv-primary)",
          foreground: "var(--rv-primary-fg)",
          soft: "var(--rv-primary-soft)",
        },
        ink: {
          DEFAULT: "#0f172a",
          muted: "#475569",
          subtle: "#64748b",
        },
        surface: {
          DEFAULT: "#ffffff",
          muted: "#f8fafc",
          card: "#ffffff",
          border: "#e2e8f0",
        },
        success: "#059669",
        warning: "#d97706",
        danger: "#dc2626",
        // Modality badges (FR-A-23).
        modality: {
          ct: "#2563eb",
          mr: "#7c3aed",
          cr: "#059669",
          dr: "#059669",
          mg: "#ec4899",
          us: "#ea580c",
          pt: "#dc2626",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Noto Sans KR",
          "sans-serif",
        ],
        mono: ["JetBrains Mono", "ui-monospace", "Menlo", "monospace"],
      },
      borderRadius: {
        card: "0.75rem",
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(15 23 42 / 0.04), 0 1px 3px 0 rgb(15 23 42 / 0.06)",
      },
    },
  },
  plugins: [],
};

export default config;
