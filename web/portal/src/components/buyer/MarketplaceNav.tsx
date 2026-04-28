import Link from "next/link";
import clsx from "clsx";

/**
 * MarketplaceNav — buyer portal top navigation, v0.3 (Kyle 2026-04-28).
 *
 * Visual locked to the v4.2.2 mockup (`docs/specs/mockups/buyer-ux-v2/v4/`):
 *   - dark navy bar, full-bleed
 *   - left:   [R] RadiVault
 *   - center: Search · Cohorts · Orders · API Docs
 *   - right:  [AC] <org>  → /account
 *
 * Sign-out is reachable via the right avatar → /account page (one click
 * less in the demo, and the avatar dropdown UX is deferred until we have
 * a designed menu). The leftExtras / rightExtras slots from v0.2 are
 * dropped — the trust-pill + locale-toggle they hosted have been
 * permanently removed (Kyle EN-only + nav cleanup rounds).
 *
 * Cohorts → /orders/new for now: that page already shows the buyer's
 * currently-selected studies. A standalone /cohorts list is a future
 * route — wire it here when it lands.
 */

function initials(label: string): string {
  // First 2 letters of the first two whitespace/punct-separated tokens,
  // uppercased. Example: "Acme AI" → "AC", "demo" → "DE".
  const cleaned = label
    .replace(/[^a-zA-Z0-9 ]+/g, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (cleaned.length === 0) return "··";
  if (cleaned.length === 1) {
    return cleaned[0].slice(0, 2).toUpperCase();
  }
  return (cleaned[0][0] + cleaned[1][0]).toUpperCase();
}

export type MarketplaceNavProps = {
  active?:
    | "/dashboard"
    | "/search"
    | "/cohorts"
    | "/orders"
    | "/docs"
    | "/account";
  /** Buyer organisation display name (from session.org). */
  org?: string | null;
  /** Buyer email — used as fallback when org is missing. */
  email?: string | null;
};

export function MarketplaceNav({ active, org, email }: MarketplaceNavProps) {
  const items = [
    { href: "/search", label: "Search", key: "/search" as const },
    { href: "/orders/new", label: "Cohorts", key: "/cohorts" as const },
    { href: "/orders", label: "Orders", key: "/orders" as const },
    { href: "/docs", label: "API Docs", key: "/docs" as const },
  ];

  const displayLabel =
    (org && org.trim()) ||
    (email ? email.split("@")[0] : null) ||
    "Account";
  const avatarInitials = initials(displayLabel);

  return (
    <header className="sticky top-0 z-20 w-full border-b border-[#1c2a44] bg-[#0d1729] text-white">
      <div className="mx-auto flex h-14 max-w-app items-center gap-8 px-6">
        {/* Brand */}
        <Link
          href="/dashboard"
          aria-label="RadiVault home"
          className="flex shrink-0 items-center gap-2.5"
        >
          <span
            aria-hidden
            className="inline-flex size-7 items-center justify-center rounded-md bg-teal-400 text-[13px] font-bold text-[#0d1729]"
          >
            R
          </span>
          <span className="text-[15px] font-semibold tracking-tight text-white">
            RadiVault
          </span>
        </Link>

        {/* Center nav */}
        <nav aria-label="Marketplace navigation" className="flex-1">
          <ul className="flex items-center gap-1">
            {items.map((it) => (
              <li key={it.key}>
                <Link
                  href={it.href}
                  className={clsx(
                    "inline-flex items-center rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors",
                    active === it.key
                      ? "bg-white/10 text-white"
                      : "text-white/70 hover:bg-white/5 hover:text-white",
                  )}
                >
                  {it.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        {/* Right: account avatar → /account */}
        <Link
          href="/account"
          aria-label={`Account — ${displayLabel}`}
          className={clsx(
            "flex shrink-0 items-center gap-2.5 rounded-md px-2 py-1 text-[13px] transition-colors",
            active === "/account"
              ? "bg-white/10 text-white"
              : "text-white/80 hover:bg-white/5 hover:text-white",
          )}
        >
          <span
            aria-hidden
            className="inline-flex size-7 items-center justify-center rounded-md bg-teal-400 text-[11px] font-bold text-[#0d1729]"
          >
            {avatarInitials}
          </span>
          <span className="font-medium">{displayLabel}</span>
        </Link>
      </div>
    </header>
  );
}
