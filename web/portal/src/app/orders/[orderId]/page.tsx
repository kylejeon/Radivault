import { MarketplaceNav } from "@/components/buyer/MarketplaceNav";
import { getBuyerSession } from "@/lib/session";
import { redirect } from "next/navigation";
import { OrderDetail } from "./OrderDetail";

/**
 * /orders/[orderId] — single order tracker (FR-BP-10).
 */
export default async function OrderDetailPage({
  params,
}: {
  params: Promise<{ orderId: string }>;
}) {
  const session = await getBuyerSession().catch(
    () => ({}) as Awaited<ReturnType<typeof getBuyerSession>>,
  );
  // Accept buyerPk OR legacy apiKey (defer-mint flow).
  if (!session?.buyerPk && !session?.apiKey) redirect("/signin");
  const { orderId } = await params;
  return (
    <div className="surface-buyer min-h-screen bg-bg">
      <MarketplaceNav active="/orders" org={session.org} email={session.email} />
      <main className="mx-auto max-w-content px-6 py-6">
        <OrderDetail orderId={orderId} />
      </main>
    </div>
  );
}
