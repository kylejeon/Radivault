/**
 * MarketingNav — top navigation for the public homepage (`/`, `/ko`).
 *
 * Distinct from `TopNav.tsx`, which serves the buyer portal (signed-in
 * surfaces). The marketing nav has no auth-aware items and holds the
 * `<LangToggle>` on the right.
 *
 * Mobile menu (≤ 767px) collapses into a disclosure (`<details>`) so the
 * component remains zero-JS on mobile aside from the LangToggle client
 * island.
 */

import Link from "next/link";
import type { Locale } from "@/lib/i18n";
import { getDict } from "@/lib/i18n";
import { LangToggle } from "./LangToggle";

export function MarketingNav({ locale }: { locale: Locale }) {
  const dict = getDict(locale);
  const koPrefix = locale === "ko" ? "/ko" : "";

  const items = [
    { href: `${koPrefix}/`, label: dict.nav.product },
    { href: `${koPrefix}/`, label: dict.nav.solutions },
    { href: `${koPrefix}/`, label: dict.nav.developers },
    { href: `/docs`, label: dict.nav.docs },
    { href: `${koPrefix === "/ko" ? "/ko" : ""}/`, label: dict.nav.pricing },
  ];

  return (
    <header className="border-b border-border bg-bg">
      <a
        href="#main"
        className="sr-only focus:not-sr-only fixed left-2 top-2 z-50 rounded-md bg-primary-600 px-3 py-2 text-sm font-medium text-white"
      >
        {dict.nav.skipToContent}
      </a>
      <div className="mx-auto flex max-w-content items-center justify-between px-6 py-4">
        <Link
          href={locale === "ko" ? "/ko" : "/"}
          className="flex items-center gap-2"
          aria-label="RadiVault home"
        >
          <span
            aria-hidden
            className="inline-flex size-7 items-center justify-center rounded-md bg-primary-600 text-white"
          >
            ◆
          </span>
          <span className="text-lg font-semibold tracking-tight text-text-strong">
            RadiVault
          </span>
        </Link>
        <nav
          aria-label={dict.nav.primaryNav}
          className="hidden tablet:block"
        >
          <ul className="flex items-center gap-1">
            {items.map((item, i) => (
              <li key={`${item.label}-${i}`}>
                <Link
                  href={item.href}
                  className="inline-flex items-center rounded-md px-3 py-1.5 text-sm font-medium text-text-muted hover:bg-bg-muted hover:text-text"
                >
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="flex items-center gap-3">
          <LangToggle locale={locale} />
          <Link
            href="/signin"
            className="inline-flex items-center rounded-md bg-primary-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-700"
          >
            {dict.nav.signIn}
          </Link>
        </div>
      </div>
    </header>
  );
}
