import type { Config } from "tailwindcss";

/**
 * Design tokens — design-spec-portal-redesign §4 (homepage + shared) layered on
 * top of design-spec-buyer-portal-demo §2 (buyer / hospital surfaces).
 *
 * Two surfaces (buyer / hospital) share this Tailwind config but expose
 * different primary palettes via CSS variables (``surface-buyer`` /
 * ``surface-hospital``) defined in globals.css.
 *
 * The portal-redesign §4 token additions are exposed as direct Tailwind
 * keys (``primary-50..900``, ``teal-50..700``, ``status-*``, ``text-*``)
 * so homepage components can address the new ladder without depending on
 * the older surface-scoped variables.
 */
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Buyer-portal-demo surface aliases (legacy — kept for /search, /orders, /hospital).
        primary: {
          DEFAULT: "var(--rv-primary)",
          foreground: "var(--rv-primary-fg)",
          soft: "var(--rv-primary-soft)",
          // portal-redesign §4.1 ladder — referenced by homepage components.
          50: "#eff6ff",
          100: "#dbeafe",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
          900: "#1e3a8a",
        },
        // portal-redesign §4.2 — Hospital teal accent (KR pages).
        teal: {
          50: "#f0fdfa",
          100: "#ccfbf1",
          600: "#0d9488",
          700: "#0f766e",
        },
        // portal-redesign §4.3 — Slate neutrals.
        bg: "#ffffff",
        "bg-muted": "#f8fafc",
        border: "#e2e8f0",
        "border-strong": "#cbd5e1",
        text: {
          DEFAULT: "#0f172a",
          muted: "#64748b",
          strong: "#020617",
        },
        // portal-redesign §4.4 — Status (light bg + dark fg variants).
        status: {
          "success-bg": "#ecfdf5",
          "success-fg": "#047857",
          "warning-bg": "#fffbeb",
          "warning-fg": "#b45309",
          "error-bg": "#fef2f2",
          "error-fg": "#b91c1c",
          "info-bg": "#eff6ff",
          "info-fg": "#1d4ed8",
        },
        // Legacy buyer-portal-demo aliases (do not remove — still consumed
        // by /search, /orders, /hospital surfaces).
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
          mg: "#9d174d", // portal-redesign FR-BP-5 — MG bumped to AA (#9d174d).
          us: "#ea580c",
          pt: "#dc2626",
          xa: "#4b5563",
        },
      },
      fontFamily: {
        // portal-redesign §4.5 stacks. Pretendard Variable is self-hosted via
        // `app/layout.tsx` link rel=preload (woff2 subset). Inter ships via
        // next/font/google in layout.
        sans: [
          "Inter",
          "Pretendard Variable",
          "Pretendard",
          "-apple-system",
          "BlinkMacSystemFont",
          "system-ui",
          "Roboto",
          "Helvetica Neue",
          "Segoe UI",
          "Apple SD Gothic Neo",
          "Noto Sans KR",
          "Malgun Gothic",
          "sans-serif",
        ],
        kr: [
          "Pretendard Variable",
          "Pretendard",
          "-apple-system",
          "BlinkMacSystemFont",
          "system-ui",
          "Roboto",
          "Helvetica Neue",
          "Segoe UI",
          "Apple SD Gothic Neo",
          "Noto Sans KR",
          "Malgun Gothic",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "SF Mono",
          "ui-monospace",
          "Menlo",
          "Consolas",
          "monospace",
        ],
      },
      fontSize: {
        // portal-redesign §4.5 type scale (4px baseline).
        xs: ["12px", { lineHeight: "16px" }],
        sm: ["14px", { lineHeight: "20px" }],
        base: ["16px", { lineHeight: "24px" }],
        lg: ["18px", { lineHeight: "28px" }],
        xl: ["20px", { lineHeight: "28px" }],
        "2xl": ["24px", { lineHeight: "32px" }],
        "3xl": ["30px", { lineHeight: "36px" }],
        "4xl": ["36px", { lineHeight: "40px" }],
        "5xl": ["48px", { lineHeight: "52px" }],
        "6xl": ["60px", { lineHeight: "64px" }],
      },
      spacing: {
        // portal-redesign §4.6 — 4px base ladder (Tailwind defaults already
        // cover most; we add the custom 0_5 = 2px slot used by trust-bar
        // bullet alignment).
        "0_5": "2px",
      },
      borderRadius: {
        // portal-redesign §4.8.
        none: "0",
        sm: "4px",
        md: "8px",
        lg: "12px",
        pill: "9999px",
        // Legacy buyer-portal-demo alias.
        card: "0.75rem",
      },
      boxShadow: {
        // portal-redesign §4.7.
        card: "0 1px 3px rgba(15,23,42,0.08), 0 1px 2px rgba(15,23,42,0.04)",
        overlay:
          "0 10px 25px rgba(15,23,42,0.10), 0 4px 10px rgba(15,23,42,0.06)",
        hero: "0 20px 40px rgba(37,99,235,0.12), 0 8px 16px rgba(15,23,42,0.08)",
      },
      maxWidth: {
        // portal-redesign §4.9 — homepage container vs. portal-app container.
        content: "1200px",
        app: "1440px",
      },
      screens: {
        // portal-redesign §4.9.
        mobile: "375px",
        tablet: "768px",
        desktop: "1280px",
        wide: "1920px",
      },
    },
  },
  plugins: [],
};

export default config;
