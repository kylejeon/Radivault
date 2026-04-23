import { TopNav } from "@/components/TopNav";
import { getBuyerSession } from "@/lib/session";
import { redirect } from "next/navigation";
import { Downloads } from "./Downloads";

export default async function DownloadsPage({
  params,
}: {
  params: Promise<{ orderId: string }>;
}) {
  const session = await getBuyerSession().catch(() => ({}) as Awaited<ReturnType<typeof getBuyerSession>>);
  if (!session?.apiKey) redirect("/signin");
  const { orderId } = await params;
  return (
    <div className="surface-buyer min-h-screen">
      <TopNav active="/orders" signedIn />
      <main className="mx-auto max-w-4xl px-6 py-6">
        <Downloads orderId={orderId} />
      </main>
    </div>
  );
}
