import { redirect } from "next/navigation";
import Link from "next/link";
import { MarketplaceNav } from "@/components/buyer/MarketplaceNav";
import { getBuyerSession } from "@/lib/session";
import { getDict } from "@/lib/i18n";
import { DashboardRecentSearches } from "./RecentSearchesIsland";

/**
 * /dashboard — design-spec-portal-redesign §11 / FR-BP-20.
 *
 * Post-sign-in landing page (5 tiles, MEDIUM-3 fix from
 * qa-report-portal-redesign). Buyers visiting `/` while signed in are
 * routed here by the middleware (web/portal/src/middleware.ts). This
 * page itself enforces the auth gate so deep links also redirect.
 *
 * Tiles:
 *  1. Active orders            — server-fetched count + "Place a new order" CTA.
 *  2. Recent searches          — client island reads localStorage (FR-BP-15).
 *  3. Pending invoices         — stub, "v0.1 offline" copy.
 *  4. API usage this month     — stub, "v0.1.1" copy.
 *  5. Platform announcements   — stub link to changelog.
 */

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const session = await getBuyerSession().catch(
    () => ({}) as Awaited<ReturnType<typeof getBuyerSession>>,
  );
  // Accept either v0.2 email/password (buyerPk) or legacy paste-mode
  // (apiKey). BLOCKER #1 fix from qa-report-d13-demo-rehearsal —
  // signin endpoint sets buyerPk + delete apiKey, so apiKey-only check
  // caused infinite /signin ↔ /dashboard redirect loop.
  if (!session?.buyerPk && !session?.apiKey) redirect("/signin");

  const dict = getDict("en");
  const tiles = dict.dashboard.tiles;

  // Best-effort active orders count. The dashboard renders even if the
  // upstream is down — we just show the empty state. v0.2 sessions have
  // no apiKey on the cookie (search uses INTERNAL_SEARCH_KEY); fall back
  // to 0 in that case (stub returns 0 either way for v0.1).
  const activeOrdersCount = session.apiKey
    ? await fetchActiveOrdersCount(session.apiKey)
    : 0;

  return (
    <div className="surface-buyer min-h-screen bg-bg">
      <MarketplaceNav active="/dashboard" />
      <main className="mx-auto max-w-content px-6 py-8" data-testid="dashboard">
        <header className="mb-6">
          <h1 className="text-2xl font-semibold text-text-strong">
            {dict.dashboard.pageTitle}
          </h1>
          <p className="mt-1 text-sm text-text-muted">
            {dict.dashboard.welcome}
            {session.buyerId ? `, ${session.buyerId}.` : "."}
          </p>
        </header>

        <div className="grid grid-cols-1 gap-4 tablet:grid-cols-2 desktop:grid-cols-3">
          {/* Tile 1 — Active orders. */}
          <Tile
            title={tiles.activeOrders.title}
            testid="dashboard-tile-active-orders"
          >
            {activeOrdersCount > 0 ? (
              <>
                <div className="text-3xl font-semibold text-text-strong">
                  {activeOrdersCount}
                </div>
                <Link
                  href="/orders"
                  className="mt-3 inline-flex text-sm font-medium text-primary-700 hover:underline"
                >
                  View orders →
                </Link>
              </>
            ) : (
              <>
                <p className="text-sm text-text-muted">
                  {tiles.activeOrders.empty}
                </p>
                <Link
                  href="/search"
                  className="mt-3 inline-flex text-sm font-medium text-primary-700 hover:underline"
                >
                  {tiles.activeOrders.cta} →
                </Link>
              </>
            )}
          </Tile>

          {/* Tile 2 — Recent searches (client island). */}
          <Tile
            title={tiles.recentSearches.title}
            testid="dashboard-tile-recent-searches"
          >
            <DashboardRecentSearches
              empty={tiles.recentSearches.empty}
              cta={tiles.recentSearches.cta}
            />
          </Tile>

          {/* Tile 3 — Pending invoices (stub). */}
          <Tile
            title={tiles.pendingInvoices.title}
            testid="dashboard-tile-pending-invoices"
          >
            <p className="text-sm text-text-muted">
              {tiles.pendingInvoices.body}
            </p>
          </Tile>

          {/* Tile 4 — API usage this month (stub). */}
          <Tile
            title={tiles.apiUsage.title}
            testid="dashboard-tile-api-usage"
          >
            <p className="text-sm text-text-muted">{tiles.apiUsage.body}</p>
          </Tile>

          {/* Tile 5 — Platform announcements. */}
          <Tile
            title={tiles.announcements.title}
            testid="dashboard-tile-announcements"
          >
            <p className="text-sm text-text">{tiles.announcements.body}</p>
            <Link
              href="/docs"
              className="mt-3 inline-flex text-sm font-medium text-primary-700 hover:underline"
            >
              {tiles.announcements.cta} →
            </Link>
          </Tile>
        </div>
      </main>
    </div>
  );
}

function Tile({
  title,
  testid,
  children,
}: {
  title: string;
  testid: string;
  children: React.ReactNode;
}) {
  return (
    <section
      className="rounded-md border border-border bg-bg p-5"
      data-testid={testid}
    >
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-muted">
        {title}
      </h2>
      {children}
    </section>
  );
}

/**
 * Best-effort buyer-orders count via the existing /api/orders BFF.
 * Returns 0 when upstream is down — we never fail the dashboard render.
 */
async function fetchActiveOrdersCount(_apiKey: string): Promise<number> {
  // The Next server can't easily call its own /api/* in RSC without
  // the cookie context, so we keep this as a stub for v0.1. A future
  // iteration (v0.1.1) lifts the count into a proper RSC fetch via
  // the upstream URL directly.
  return 0;
}
