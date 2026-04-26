"use client";

/**
 * <LocaleToggle> + <LocaleProvider> + useLocale() — buyer-search-v3
 * FR-V3-UI-8.1 (QA HIGH-3 / BL-2).
 *
 * Runtime EN ↔ KR locale toggle that flips the active language **in-place**
 * (no full page navigation, no SSR re-fetch). The mockup `search.html` ships
 * a `.locale-toggle` button group in the top-right; this component is the
 * React port.
 *
 *   ┌────────┬──────────┐
 *   │ EN     │ 한국어    │
 *   └────────┴──────────┘
 *
 * Wiring:
 *   <LocaleProvider initial="en">    // SSR initial; hydrates from localStorage
 *     <LocaleToggle />               // call setLocale() on click
 *     <child useLocale() … />        // re-renders on context change
 *   </LocaleProvider>
 *
 * Persistence:
 *   - localStorage key `radivault.locale` survives reload.
 *   - cookie `radivault_locale` (365d, SameSite=Lax) is also set so future
 *     SSR requests can choose KR before React mounts (parity with the
 *     existing `<LangToggle>` for the marketing pages).
 *   - `<body data-locale="ko">` lets non-React surfaces (CSS) react to the
 *     change — useful for Pretendard vs Inter font swap if the design-spec
 *     needs that later.
 *
 * Why an island + context (vs URL prefix):
 *   - URL-prefix (`/ko/search`) requires a SSR round-trip and blows away
 *     React local state (selection set, cart, sort, debounce timer).
 *   - The portal already has a separate cookie-based marketing toggle. The
 *     buyer search page is single-route and richly stateful → context is
 *     the right shape (the dev-spec explicitly notes "URL prefix OR
 *     sessionStorage/body-data").
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { Locale } from "@/lib/i18n";

const STORAGE_KEY = "radivault.locale";
const COOKIE_NAME = "radivault_locale";
const COOKIE_TTL_DAYS = 365;

type LocaleContextValue = {
  locale: Locale;
  setLocale: (next: Locale) => void;
};

const LocaleContext = createContext<LocaleContextValue | null>(null);

function setLocaleCookie(locale: Locale) {
  if (typeof document === "undefined") return;
  const maxAge = COOKIE_TTL_DAYS * 24 * 60 * 60;
  const secure =
    typeof window !== "undefined" && window.location.protocol === "https:"
      ? "; Secure"
      : "";
  document.cookie = `${COOKIE_NAME}=${locale}; Path=/; Max-Age=${maxAge}; SameSite=Lax${secure}`;
}

function syncBody(locale: Locale) {
  if (typeof document === "undefined") return;
  document.body.setAttribute("data-locale", locale);
}

export function LocaleProvider({
  initial = "en",
  children,
}: {
  initial?: Locale;
  children: ReactNode;
}) {
  const [locale, setLocaleState] = useState<Locale>(initial);

  // Hydrate from localStorage once (cookie + body data attr stay in sync
  // with whatever the user chose last visit). Defer to layout-effect time
  // to avoid the SSR/CSR text mismatch warning — the initial render uses
  // the prop, then we swap on mount if storage differs.
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored === "en" || stored === "ko") {
        if (stored !== locale) setLocaleState(stored);
        syncBody(stored);
      } else {
        syncBody(locale);
      }
    } catch {
      syncBody(locale);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    if (typeof window !== "undefined") {
      try {
        window.localStorage.setItem(STORAGE_KEY, next);
      } catch {
        /* quota — ignore */
      }
    }
    setLocaleCookie(next);
    syncBody(next);
  }, []);

  const value = useMemo(() => ({ locale, setLocale }), [locale, setLocale]);
  return (
    <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>
  );
}

/**
 * Hook returns the current locale + setter. Falls back to ("en", noop) if
 * called outside `<LocaleProvider>` so legacy v2 surfaces keep working.
 */
export function useLocale(): LocaleContextValue {
  const ctx = useContext(LocaleContext);
  if (ctx) return ctx;
  return { locale: "en", setLocale: () => {} };
}

export type LocaleToggleProps = {
  /** Visual variant: "dark" matches the v3 navy top-bar; "light" matches a white sub-bar. */
  variant?: "dark" | "light";
  className?: string;
};

export function LocaleToggle({
  variant = "dark",
  className,
}: LocaleToggleProps) {
  const { locale, setLocale } = useLocale();

  const isDark = variant === "dark";
  const wrapStyle: React.CSSProperties = {
    display: "inline-flex",
    background: isDark ? "rgba(255,255,255,0.08)" : "var(--rv-stone-100)",
    borderRadius: 4,
    padding: 2,
  };

  function btn(target: Locale, labelEn: string, labelKo: string) {
    const active = locale === target;
    const style: React.CSSProperties = {
      padding: "4px 10px",
      fontSize: 12,
      fontWeight: 600,
      cursor: "pointer",
      border: "none",
      borderRadius: 3,
      background: active
        ? isDark
          ? "var(--rv-teal-500)"
          : "var(--rv-navy-900)"
        : "transparent",
      color: active
        ? isDark
          ? "var(--rv-navy-900)"
          : "#fff"
        : isDark
          ? "rgba(255,255,255,0.7)"
          : "var(--rv-stone-700)",
    };
    return (
      <button
        type="button"
        role="tab"
        aria-selected={active}
        aria-current={active ? "true" : undefined}
        data-testid={`v3-locale-toggle-${target}`}
        onClick={() => setLocale(target)}
        style={style}
      >
        {target === "en" ? labelEn : labelKo}
      </button>
    );
  }

  return (
    <div
      role="tablist"
      aria-label="Switch language"
      data-testid="v3-locale-toggle"
      className={className}
      style={wrapStyle}
    >
      {btn("en", "EN", "EN")}
      {btn("ko", "한국어", "한국어")}
    </div>
  );
}
