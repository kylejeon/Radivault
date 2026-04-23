import { TopNav } from "@/components/TopNav";
import { getBuyerSession } from "@/lib/session";
import { redirect } from "next/navigation";
import { SearchApp } from "./SearchApp";

export default async function SearchPage() {
  const session = await getBuyerSession().catch(() => ({}) as Awaited<ReturnType<typeof getBuyerSession>>);
  if (!session?.apiKey) redirect("/signin");
  return (
    <div className="surface-buyer min-h-screen">
      <TopNav active="/search" signedIn />
      <main className="mx-auto max-w-7xl px-6 py-6">
        <SearchApp />
      </main>
    </div>
  );
}
