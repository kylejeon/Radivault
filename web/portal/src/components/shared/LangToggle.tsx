"use client";

/**
 * LangToggle — design-spec-portal-redesign §5.9 ({#lang-toggle-v1}).
 *
 * Sits in TopNav (right) and Footer (right). On click:
 *   1. Drops cookie `radivault_locale` (365d, SameSite=Lax, Secure in prod).
 *   2. Navigates to the alternate path computed by `alternatePath()`
 *      in `lib/i18n.ts` (e.g. "/" -> "/ko", "/contact" -> "/ko/contact").
 *
 * The cookie is read by future SSR handlers (FR-HP-11). For v0.1 we still
 * fall back to filesystem routing (`/ko/...`) so the cookie is purely a
 * "next-visit hint", not a runtime required input.
 */

import { usePathname } from "next/navigation";
import clsx from "clsx";
import type { MouseEvent } from "react";
import type { Locale } from "@/lib/i18n";
import { alternatePath, getDict } from "@/lib/i18n";

const COOKIE_TTL_DAYS = 365;

function setLocaleCookie(locale: Locale) {
  if (typeof document === "undefined") return;
  const maxAge = COOKIE_TTL_DAYS * 24 * 60 * 60;
  const secure =
    typeof window !== "undefined" && window.location.protocol === "https:"
      ? "; Secure"
      : "";
  document.cookie = `radivault_locale=${locale}; Path=/; Max-Age=${maxAge}; SameSite=Lax${secure}`;
}

export function LangToggle({ locale }: { locale: Locale }) {
  const pathname = usePathname() ?? "/";
  const dict = getDict(locale);
  const enHref = alternatePath(pathname, "en");
  const koHref = alternatePath(pathname, "ko");

  // We use plain anchors instead of <Link> on purpose: this lets us set
  // the cookie synchronously and then trigger a full reload so the new
  // locale becomes visible without depending on Next's RSC cache.
  function handleClick(target: Locale, href: string) {
    return (event: MouseEvent<HTMLAnchorElement>) => {
      event.preventDefault();
      setLocaleCookie(target);
      if (typeof window !== "undefined") {
        window.location.href = href;
      }
    };
  }

  return (
    <div
      className="inline-flex items-center gap-1 text-sm"
      role="group"
      aria-label={dict.langToggle.ariaLabel}
      data-testid="lang-toggle"
    >
      <a
        href={enHref}
        onClick={handleClick("en", enHref)}
        aria-current={locale === "en" ? "page" : undefined}
        className={clsx(
          "px-1",
          locale === "en"
            ? "font-semibold text-text underline decoration-primary-600 decoration-2 underline-offset-4"
            : "text-text-muted hover:text-text",
        )}
        data-testid="lang-toggle-en"
      >
        {dict.langToggle.en}
      </a>
      <span aria-hidden className="text-text-muted">
        |
      </span>
      <a
        href={koHref}
        onClick={handleClick("ko", koHref)}
        aria-current={locale === "ko" ? "page" : undefined}
        className={clsx(
          "px-1",
          locale === "ko"
            ? "font-semibold text-text underline decoration-primary-600 decoration-2 underline-offset-4"
            : "text-text-muted hover:text-text",
        )}
        data-testid="lang-toggle-ko"
      >
        {dict.langToggle.ko}
      </a>
    </div>
  );
}
