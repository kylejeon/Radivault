import { TopNav } from "@/components/TopNav";
import { getBuyerSession } from "@/lib/session";
import { redirect } from "next/navigation";
import { OrdersList } from "./OrdersList";

export default async function OrdersPage() {
  const session = await getBuyerSession().catch(() => ({}) as Awaited<ReturnType<typeof getBuyerSession>>);
  if (!session?.apiKey) redirect("/signin");
  return (
    <div className="surface-buyer min-h-screen">
      <TopNav active="/orders" signedIn />
      <main className="mx-auto max-w-5xl px-6 py-6">
        <h1 className="mb-4 text-2xl font-semibold">Orders</h1>
        <OrdersList />
      </main>
    </div>
  );
}
