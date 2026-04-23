import { redirect } from "next/navigation";
import { getHospitalSession } from "@/lib/session";
import { HospitalDashboard } from "./HospitalDashboard";
import { HospitalHeader } from "./HospitalHeader";

/**
 * Hospital Dashboard (design-spec §6, all in Korean).
 *
 * Authenticated via ``rv_hospital_session`` cookie (iron-session). The
 * unauthed path is ``/hospital/signin``.
 */
export default async function HospitalPage() {
  const session = await getHospitalSession().catch(() => ({}) as Awaited<ReturnType<typeof getHospitalSession>>);
  if (!session?.hospitalId) redirect("/hospital/signin");
  return (
    <div className="surface-hospital min-h-screen bg-surface-muted">
      <HospitalHeader hospitalId={session.hospitalId} />
      <main className="mx-auto max-w-6xl px-6 py-6">
        <HospitalDashboard />
      </main>
    </div>
  );
}
