import { redirect } from "next/navigation";

import { TopNav } from "@/components/TopNav";
import { getBuyerSession } from "@/lib/session";
import { getDict } from "@/lib/i18n";
import { SignInForm } from "../../signin/SignInForm";

export default async function KoSignInPage() {
  const session = await getBuyerSession().catch(
    () => ({}) as Awaited<ReturnType<typeof getBuyerSession>>,
  );
  if (session?.buyerPk || session?.apiKey) redirect("/search");
  const dict = getDict("ko");
  return (
    <div className="surface-buyer min-h-screen bg-bg">
      <TopNav active="/ko/signin" signedIn={false} />
      <main className="mx-auto max-w-md px-6 py-16">
        <h1 className="text-2xl font-semibold text-text-strong">
          {dict.auth.signin.pageTitle}
        </h1>
        <p className="mt-1 text-sm text-text-muted">
          {dict.auth.signin.pageSubtitle}
        </p>
        <div className="mt-6">
          <SignInForm locale="ko" />
        </div>
      </main>
    </div>
  );
}
