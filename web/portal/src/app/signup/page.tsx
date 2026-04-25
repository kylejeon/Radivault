import { redirect } from "next/navigation";

import { TopNav } from "@/components/TopNav";
import { getBuyerSession } from "@/lib/session";
import { env } from "@/lib/env";
import { getDict } from "@/lib/i18n";
import { SignupForm } from "./SignupForm";

/**
 * /signup — design-spec-buyer-auth §6 wireframe (full page, EN).
 *
 * Server component: redirects to /search if already signed in. Renders
 * the client SignupForm island with locale + skip-flag passed as props
 * so the form knows whether to show the OTP modal after submit.
 */
export default async function SignupPage() {
  const session = await getBuyerSession().catch(
    () => ({}) as Awaited<ReturnType<typeof getBuyerSession>>,
  );
  if (session?.buyerPk || session?.apiKey) redirect("/search");
  const dict = getDict("en");
  return (
    <div className="surface-buyer min-h-screen bg-bg">
      <TopNav active="/signup" signedIn={false} />
      <main className="mx-auto max-w-md px-6 py-12">
        <h1 className="text-2xl font-semibold text-text-strong">
          {dict.auth.signup.pageTitle}
        </h1>
        <p className="mt-2 text-sm text-text-muted">
          {dict.auth.signup.pageSubtitle}
        </p>
        <div className="mt-6">
          <SignupForm locale="en" skipEmailVerify={env.buyerAuthSkipEmailVerify} />
        </div>
      </main>
    </div>
  );
}
