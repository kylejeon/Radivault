import { TopNav } from "@/components/TopNav";
import { getBuyerSession } from "@/lib/session";
import { redirect } from "next/navigation";
import { SignInForm } from "./SignInForm";

/**
 * A-2 Sign-in (design-spec §5 / FR-A-3..FR-A-4).
 *
 * Single-field form. Submission POSTs to the BFF which:
 * 1. validates rv_live_/rv_test_ prefix
 * 2. calls metadata-index /v1/search/facets with the raw key
 * 3. on 200, stores the (encrypted) key in the rv_session cookie
 * 4. on failure, surfaces ERR_AUTH_FORMAT or ERR_AUTH_INVALID
 */
export default async function SignInPage() {
  const session = await getBuyerSession().catch(() => ({}) as Awaited<ReturnType<typeof getBuyerSession>>);
  if (session?.apiKey) redirect("/search");
  return (
    <div className="surface-buyer">
      <TopNav active="/signin" signedIn={false} />
      <main className="mx-auto max-w-md px-6 py-16">
        <h1 className="text-2xl font-semibold">Sign in</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Paste your <code>rv_live_…</code> API key to access search and
          orders. Keys are issued by RadiVault sales; contact{" "}
          <a className="underline" href="mailto:sales@radivault.io">
            sales@radivault.io
          </a>
          .
        </p>
        <div className="mt-6">
          <SignInForm />
        </div>
      </main>
    </div>
  );
}
