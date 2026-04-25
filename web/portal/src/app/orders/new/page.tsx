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
  if (!session?.apiKey) redirect("/signin");
  return (
    <div className="surface-buyer min-h-screen bg-bg">
      <MarketplaceNav active="/orders" />
      <main className="mx-auto max-w-content px-6 py-6">
        <OrderReviewClient locale="en" />
      </main>
    </div>
  );
}
