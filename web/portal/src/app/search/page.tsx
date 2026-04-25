import { MarketplaceNav } from "@/components/buyer/MarketplaceNav";
import { getBuyerSession } from "@/lib/session";
import { redirect } from "next/navigation";
import { SearchApp } from "./SearchApp";

/**
 * /search — design-spec-portal-redesign §12.1, FR-BP-3.
 *
 * 3-pane layout (facets · results · cohort). The legacy
 * `<components/TopNav>` is replaced by the v0.2 `<MarketplaceNav>` per
 * FR-BP-12 (adds Account entry + RadiVault Marketplace wordmark).
 */
export default async function SearchPage() {
  const session = await getBuyerSession().catch(
    () => ({}) as Awaited<ReturnType<typeof getBuyerSession>>,
  );
  if (!session?.apiKey) redirect("/signin");
  return (
    <div className="surface-buyer min-h-screen bg-bg">
      <MarketplaceNav active="/search" />
      <main className="mx-auto max-w-app">
        <SearchApp locale="en" />
      </main>
    </div>
  );
}
