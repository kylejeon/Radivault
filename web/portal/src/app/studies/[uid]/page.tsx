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
  if (!session?.apiKey) redirect("/signin");
  const { uid } = await params;
  return (
    <div className="surface-buyer min-h-screen bg-bg">
      <MarketplaceNav active="/search" />
      <main className="mx-auto max-w-content px-6 py-6">
        <StudyDetailClient uid={uid} locale="en" />
      </main>
    </div>
  );
}
