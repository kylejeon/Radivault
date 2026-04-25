import { redirect } from "next/navigation";
import { getHospitalSession } from "@/lib/session";
import { HospitalHeader } from "../HospitalHeader";
import { FooterKr } from "@/components/shared/FooterKr";
import { FloatingContactButton } from "@/components/shared/FloatingContactButton";
import { QuotaPanel } from "./QuotaPanel";
import { getDict } from "@/lib/i18n";

/**
 * /hospital/quota — design-spec §18.3.
 *
 * Surfaces the same /api/hospital/me/quota endpoint as the dashboard
 * tile but with the full daily / monthly / concurrent / ruleset / salt /
 * pixel-engine breakdown. v0.1 = display-only — limits are not yet
 * enforced server-side (FR-HO-6 + dev-spec §4.4 FR-INF-7 note). The
 * "v0.1 한도 집행 없음" disclaimer fires unconditionally.
 */

export default async function HospitalQuotaPage() {
  const session = await getHospitalSession().catch(
    () => ({}) as Awaited<ReturnType<typeof getHospitalSession>>,
  );
  if (!session?.hospitalId) redirect("/hospital/signin");
  const dict = getDict("ko");
  return (
    <div className="surface-hospital min-h-screen bg-bg-muted">
      <HospitalHeader hospitalId={session.hospitalId} />
      <main className="mx-auto max-w-content px-6 py-6 lang-ko">
        <div className="flex items-baseline justify-between">
          <h1 className="text-xl font-semibold text-text-strong">
            {dict.hospital.title.quota}
          </h1>
          <span className="text-sm text-text-muted">{session.hospitalId}</span>
        </div>
        <QuotaPanel />
      </main>
      <FooterKr variant="hospital" />
      <FloatingContactButton />
    </div>
  );
}
