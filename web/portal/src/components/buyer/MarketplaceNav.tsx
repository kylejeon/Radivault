import Link from "next/link";
import clsx from "clsx";
import { getDict, type Locale } from "@/lib/i18n";

/**
 * MarketplaceNav — design-spec-portal-redesign §12 / FR-BP-12.
 *
 * Buyer-portal top navigation for the redesigned `/search`, `/studies/*`,
 * `/orders*`, `/account` routes. Distinct from the legacy `<TopNav>`
 * (kept for the demo surfaces that haven't been ported yet) — this nav
 * adds the `Account` entry, the "RadiVault Marketplace" wordmark, and
 * exposes Sign-out as a form post.
 */

export function MarketplaceNav({
  active,
  locale = "en",
}: {
  active?: "/dashboard" | "/search" | "/orders" | "/docs" | "/account";
  locale?: Locale;
}) {
  const dict = getDict(locale);
  const items = [
    { href: "/search", label: dict.buyerNav.search, key: "/search" },
    { href: "/orders", label: dict.buyerNav.orders, key: "/orders" },
    { href: "/docs", label: dict.buyerNav.docs, key: "/docs" },
    { href: "/account", label: dict.buyerNav.account, key: "/account" },
  ] as const;

  return (
    <header className="sticky top-0 z-20 border-b border-border bg-bg">
      <div className="mx-auto flex h-16 max-w-app items-center justify-between px-6">
        <Link
          href="/dashboard"
          aria-label="RadiVault Marketplace home"
          className="flex items-center gap-2"
        >
          <span
            aria-hidden
            className="inline-flex size-7 items-center justify-center rounded-md bg-primary-600 text-white"
          >
            ◆
          </span>
          <span className="text-base font-semibold tracking-tight text-text-strong">
            {dict.buyerNav.wordmark}
          </span>
        </Link>
        <nav aria-label="Marketplace navigation">
          <ul className="flex items-center gap-1">
            {items.map((it) => (
              <li key={it.key}>
                <Link
                  href={it.href}
                  className={clsx(
                    "inline-flex items-center rounded-md px-3 py-1.5 text-sm font-medium",
                    active === it.key
                      ? "bg-primary-50 text-primary-700"
                      : "text-text-muted hover:bg-bg-muted hover:text-text",
                  )}
                >
                  {it.label}
                </Link>
              </li>
            ))}
            <li className="ml-3">
              <form action="/api/session/delete" method="post">
                <button
                  type="submit"
                  className="rounded-md border border-border px-3 py-1.5 text-sm text-text-muted hover:bg-bg-muted"
                >
                  {dict.buyerNav.signOut}
                </button>
              </form>
            </li>
          </ul>
        </nav>
      </div>
    </header>
  );
}
