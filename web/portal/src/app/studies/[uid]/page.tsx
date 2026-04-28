import { MarketplaceNav } from "@/components/buyer/MarketplaceNav";
import { getBuyerSession } from "@/lib/session";
import { redirect } from "next/navigation";
import { StudyDetailClient } from "./StudyDetailClient";

/**
 * /studies/[uid] — design-spec-portal-redesign §12.2 / FR-BP-8.
 *
 * Server entry: gates on iron-session, then hands off to a client island
 * that fetches `/api/search/studies/[uid]` and renders
 * `<StudyDetailPanel>`. 404 / 403 are surfaced via §14.3 page-level error.
 */
export default async function StudyDetailPage({
  params,
}: {
  params: Promise<{ uid: string }>;
}) {
  const session = await getBuyerSession().catch(
    () => ({}) as Awaited<ReturnType<typeof getBuyerSession>>,
  );
  // Accept either v0.2 email/password (buyerPk) or legacy paste-mode
  // (apiKey). BLOCKER #1 fix from qa-report-d13-demo-rehearsal —
  // signin endpoint sets buyerPk + delete apiKey, so apiKey-only check
  // caused infinite /signin ↔ /studies/[uid] redirect loop.
  if (!session?.buyerPk && !session?.apiKey) redirect("/signin");
  const { uid } = await params;
  // Full-bleed shell — the v3 study-detail layout owns its own padding (sub-bar
  // is full-width, dark viewer pane goes edge-to-edge). The legacy
  // `max-w-content px-6 py-6` wrapper would cap it to 1280px and add a white
  // gutter that breaks the dark canvas / right-rail composition.
  return (
    <div className="surface-buyer min-h-screen bg-bg">
      <MarketplaceNav active="/search" />
      <StudyDetailClient uid={uid} locale="en" />
    </div>
  );
}
