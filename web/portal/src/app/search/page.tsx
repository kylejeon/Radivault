import { MarketplaceNav } from "@/components/buyer/MarketplaceNav";
import { SearchAppV3 } from "@/components/buyer/v3/SearchAppV3";
import { getBuyerSession } from "@/lib/session";
import { redirect } from "next/navigation";

/**
 * /search — buyer-search-v3 (FR-V3-UI-1) supersedes the v2 3-pane layout
 * with the v3 dense 13-column table + 5-group accordion sidebar + KCD
 * triple-ontology autocomplete. Old SearchApp.tsx kept for reference but
 * no longer routed.
 *
 * BLOCKER #1 fix from qa-report-d13-demo-rehearsal preserved — accept
 * either v0.2 email/password (buyerPk) or legacy paste-mode (apiKey).
 *
 * EN-only buyer portal (Kyle 2026-04-28, design-spec-dicom-viewer v0.3.2):
 * the previous LocaleProvider + MarketplaceNavLocaleToggle (EN/한국어
 * tab pair) is removed — global AI buyers are the sole audience and KO
 * surfacing moves to the future hospital console. SearchAppV3's
 * `useLocale()` hook still works because it falls back to ("en", noop)
 * outside a provider (see LocaleToggle.tsx).
 */
export default async function SearchPage() {
  const session = await getBuyerSession().catch(
    () => ({}) as Awaited<ReturnType<typeof getBuyerSession>>,
  );
  if (!session?.buyerPk && !session?.apiKey) redirect("/signin");

  return (
    <div className="surface-buyer min-h-screen bg-bg">
      <MarketplaceNav active="/search" />
      <main className="mx-auto max-w-app">
        <SearchAppV3 locale="en" />
      </main>
    </div>
  );
}
