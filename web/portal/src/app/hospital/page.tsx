import { redirect } from "next/navigation";
import { getHospitalSession } from "@/lib/session";
import { HospitalDashboard } from "./HospitalDashboard";
import { HospitalHeader } from "./HospitalHeader";
import { FooterKr } from "@/components/shared/FooterKr";
import { FloatingContactButton } from "@/components/shared/FloatingContactButton";

/**
 * Hospital console (design-spec §18.1, KR-only).
 *
 * Authenticated via the ``rv_hospital_session`` cookie (iron-session).
 * The unauth path is ``/hospital/signin``. Session cookie is also the
 * sole source of `hospital_id` — the BFF layer never trusts a header
 * for this (FR-HO-12 / AC-B-8 cross-tenant isolation).
 */
export default async function HospitalPage() {
  const session = await getHospitalSession().catch(
    () => ({}) as Awaited<ReturnType<typeof getHospitalSession>>,
  );
  if (!session?.hospitalId) redirect("/hospital/signin");
  return (
    <div className="surface-hospital min-h-screen bg-bg-muted">
      <HospitalHeader hospitalId={session.hospitalId} />
      <main className="mx-auto max-w-content px-6 py-6">
        <div className="mb-4 text-sm text-text-muted">
          <span className="font-semibold text-text-strong">{session.hospitalId}</span> · 안녕하세요, 운영자님
        </div>
        <HospitalDashboard hospitalId={session.hospitalId} />
      </main>
      <FooterKr variant="hospital" />
      <FloatingContactButton />
    </div>
  );
}
