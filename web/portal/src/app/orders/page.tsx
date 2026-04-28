import { MarketplaceNav } from "@/components/buyer/MarketplaceNav";
import { getBuyerSession } from "@/lib/session";
import { redirect } from "next/navigation";
import { OrdersList } from "./OrdersList";

/**
 * /orders — orders list (FR-BP-10). Uses the v0.2 `<MarketplaceNav>`.
 */
export default async function OrdersPage() {
  const session = await getBuyerSession().catch(
    () => ({}) as Awaited<ReturnType<typeof getBuyerSession>>,
  );
  // Accept buyerPk OR legacy apiKey (defer-mint flow).
  if (!session?.buyerPk && !session?.apiKey) redirect("/signin");
  return (
    <div className="surface-buyer min-h-screen bg-bg">
      <MarketplaceNav active="/orders" org={session.org} email={session.email} />
      <main className="mx-auto max-w-content px-6 py-6">
        <h1 className="mb-4 text-2xl font-semibold text-text-strong">Orders</h1>
        <OrdersList />
      </main>
    </div>
  );
}
