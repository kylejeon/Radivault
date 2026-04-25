import { MarketplaceNav } from "@/components/buyer/MarketplaceNav";
import { getBuyerSession } from "@/lib/session";
import { redirect } from "next/navigation";
import { AccountClient } from "./AccountClient";

/**
 * /account — design-spec-portal-redesign §12.4 / FR-BP-13.
 *
 * Profile + API keys + Billing stub. The session apiKey is forwarded into
 * the client island as a Stripe-style mask only — the raw value never leaves
 * the server (httpOnly iron-session cookie). K-11 reveal flow is a stub
 * (button is wired but the actual fetch is deferred to v0.1.1).
 */
export default async function AccountPage() {
  const session = await getBuyerSession().catch(
    () => ({}) as Awaited<ReturnType<typeof getBuyerSession>>,
  );
  if (!session?.apiKey) redirect("/signin");

  // Stripe-style mask: 8-char prefix + ... + last 8 chars (server-rendered).
  const apiKey = session.apiKey;
  const masked = maskApiKey(apiKey);

  return (
    <div className="surface-buyer min-h-screen bg-bg">
      <MarketplaceNav active="/account" />
      <main className="mx-auto max-w-content px-6 py-6">
        <AccountClient
          apiKeyMasked={masked}
          buyerId={session.buyerId ?? "buy_demo001"}
          tier={session.tier ?? "preview"}
          signedInAt={session.signedInAt ?? Date.now()}
          locale="en"
        />
      </main>
    </div>
  );
}

function maskApiKey(key: string): string {
  if (!key) return "rv_live_***...****";
  // Match the design-spec example: `rv_live_***...****cf4ec164`
  const prefix = key.slice(0, 8); // "rv_live_"
  const tail = key.slice(-8);
  return `${prefix}***...****${tail}`;
}
