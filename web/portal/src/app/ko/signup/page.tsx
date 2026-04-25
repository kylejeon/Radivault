import { redirect } from "next/navigation";

import { TopNav } from "@/components/TopNav";
import { getBuyerSession } from "@/lib/session";
import { env } from "@/lib/env";
import { getDict } from "@/lib/i18n";
import { SignupForm } from "../../signup/SignupForm";

/**
 * /ko/signup — design-spec-buyer-auth §11 i18n + §5.4.2 PIPA 4-way.
 */
export default async function KoSignupPage() {
  const session = await getBuyerSession().catch(
    () => ({}) as Awaited<ReturnType<typeof getBuyerSession>>,
  );
  if (session?.buyerPk || session?.apiKey) redirect("/search");
  const dict = getDict("ko");
  return (
    <div className="surface-buyer min-h-screen bg-bg">
      <TopNav active="/ko/signup" signedIn={false} />
      <main className="mx-auto max-w-md px-6 py-12">
        <h1 className="text-2xl font-semibold text-text-strong">
          {dict.auth.signup.pageTitle}
        </h1>
        <p className="mt-2 text-sm text-text-muted">
          {dict.auth.signup.pageSubtitle}
        </p>
        <div className="mt-6">
          <SignupForm locale="ko" skipEmailVerify={env.buyerAuthSkipEmailVerify} />
        </div>
      </main>
    </div>
  );
}
