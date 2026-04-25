import { redirect } from "next/navigation";
import { getHospitalSession } from "@/lib/session";
import { HospitalHeader } from "../HospitalHeader";
import { FooterKr } from "@/components/shared/FooterKr";
import { FloatingContactButton } from "@/components/shared/FloatingContactButton";
import { AuditLogList } from "./AuditLogList";
import { getDict } from "@/lib/i18n";

/**
 * /hospital/audit — design-spec §18.2.
 *
 * v0.1 implementation: time-ordered list of the most recent 20 audit
 * events (FR-HO-7). Cursor pagination + filter chips ship in v0.1.1.
 */

export default async function HospitalAuditPage() {
  const session = await getHospitalSession().catch(
    () => ({}) as Awaited<ReturnType<typeof getHospitalSession>>,
  );
  if (!session?.hospitalId) redirect("/hospital/signin");
  const dict = getDict("ko");
  return (
    <div className="surface-hospital min-h-screen bg-bg-muted">
      <HospitalHeader hospitalId={session.hospitalId} />
      <main className="mx-auto max-w-content px-6 py-6 lang-ko">
        <h1 className="text-xl font-semibold text-text-strong">
          {dict.hospital.audit.title}
        </h1>
        <p className="mt-1 text-xs text-text-muted">
          {dict.hospital.audit.stubNote}
        </p>
        <section className="card mt-4 p-4">
          <AuditLogList />
        </section>
      </main>
      <FooterKr variant="hospital" />
      <FloatingContactButton />
    </div>
  );
}
