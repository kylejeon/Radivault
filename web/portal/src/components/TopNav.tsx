import Link from "next/link";
import clsx from "clsx";

/**
 * Buyer-surface top navigation (design-spec §3, Shell).
 *
 * Items: Logo · Search · Orders · Downloads · Docs · Sign-in or Sign-out.
 * The ``active`` prop is a simple path prefix match; the route we're on
 * highlights its tab with the primary colour.
 */
export function TopNav({ active, signedIn }: { active?: string; signedIn: boolean }) {
  const items = [
    { href: "/", label: "Home" },
    { href: "/search", label: "Search", authed: true },
    { href: "/orders", label: "Orders", authed: true },
    { href: "/docs", label: "Docs" },
  ];
  return (
    <header className="border-b border-surface-border bg-white">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-center gap-2">
          <div className="size-7 rounded bg-primary" aria-hidden />
          <span className="text-lg font-semibold tracking-tight">RadiVault</span>
        </Link>
        <nav aria-label="Main navigation">
          <ul className="flex items-center gap-1">
            {items.map((i) => {
              if (i.authed && !signedIn) return null;
              const isActive = active === i.href;
              return (
                <li key={i.href}>
                  <Link
                    href={i.href}
                    className={clsx(
                      "inline-flex items-center rounded-md px-3 py-1.5 text-sm font-medium",
                      isActive
                        ? "bg-primary-soft text-primary"
                        : "text-ink-muted hover:bg-surface-muted hover:text-ink",
                    )}
                  >
                    {i.label}
                  </Link>
                </li>
              );
            })}
            <li className="ml-4">
              {signedIn ? (
                <form action="/api/session/delete" method="post">
                  <button
                    type="submit"
                    className="rounded-md border border-surface-border px-3 py-1.5 text-sm text-ink-muted hover:bg-surface-muted"
                  >
                    Sign out
                  </button>
                </form>
              ) : (
                <Link
                  href="/signin"
                  className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground"
                >
                  Sign in
                </Link>
              )}
            </li>
          </ul>
        </nav>
      </div>
    </header>
  );
}
