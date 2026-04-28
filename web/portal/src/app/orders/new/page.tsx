import { MarketplaceNav } from "@/components/buyer/MarketplaceNav";
import { getBuyerSession } from "@/lib/session";
import { redirect } from "next/navigation";
import { OrderReviewClient } from "./OrderReviewClient";

/**
 * /orders/new — design-spec-portal-redesign §12.3 / FR-BP-9.
 *
 * Promotes the legacy `<ReviewOrderModal>` to a full page route. Cohort is
 * read from sessionStorage (set by the search 3-pane). DUA agreement +
 * "Place order" CTA submit through the existing BFF `POST /api/orders`.
 */
export default async function OrderReviewPage() {
  const session = await getBuyerSession().catch(
    () => ({}) as Awaited<ReturnType<typeof getBuyerSession>>,
  );
  // Accept either v0.2 email/password (buyerPk) or legacy paste-mode apiKey,
  // matching the BLOCKER #1 fix already applied to /search. Without this,
  // every email/password buyer (now the default after defer-mint) bounces
  // back to /signin → /search and the Review-order CTA appears broken.
  if (!session?.buyerPk && !session?.apiKey) redirect("/signin");
  return (
    <div className="surface-buyer min-h-screen bg-bg">
      <MarketplaceNav active="/cohorts" org={session.org} email={session.email} />
      <main className="mx-auto max-w-content px-6 py-6">
        <OrderReviewClient locale="en" />
      </main>
    </div>
  );
}
