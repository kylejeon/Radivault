import { redirect } from "next/navigation";

import { MarketplaceNav } from "@/components/buyer/MarketplaceNav";
import { getBuyerSession } from "@/lib/session";
import { getAuthStore } from "@/lib/auth/store";
import { maskKid, maskApiKey } from "@/lib/auth/api-key";
import { AccountClient } from "./AccountClient";

/**
 * /account — design-spec-buyer-auth §6 wireframe.
 *
 * Two session shapes are supported during the 90-day deprecation window:
 *   1. v0.2 email/password session  (buyerPk + email + buyerId set)
 *   2. v0.1 legacy API-key paste    (apiKey set; no buyerPk)
 *
 * Path #2 falls back to the previous read-from-cookie behaviour
 * (mask the cookie's apiKey directly) so the legacy flow keeps working.
 */
export default async function AccountPage() {
  const session = await getBuyerSession().catch(
    () => ({}) as Awaited<ReturnType<typeof getBuyerSession>>,
  );

  // Either auth path is acceptable.
  if (!session?.buyerPk && !session?.apiKey) redirect("/signin");

  let initialKey = {
    kid: null as string | null,
    masked: null as string | null,
    createdAt: null as string | null,
    lastUsedAt: null as string | null,
  };
  let buyerId = session.buyerId ?? "buy_demo001";
  const tier = session.tier ?? "preview";
  const signedInAt = session.signedInAt ?? Date.now();
  const email = session.email ?? null;
  const locale = (session.locale ?? "en") as "en" | "ko";

  if (session.buyerPk) {
    // v0.2 path — query store
    const store = getAuthStore();
    const key = await store.findActiveApiKey(session.buyerPk);
    if (key) {
      initialKey = {
        kid: key.kid,
        masked: maskKid(key.kid),
        createdAt: new Date(key.createdAt).toISOString(),
        lastUsedAt: key.lastUsedAt ? new Date(key.lastUsedAt).toISOString() : null,
      };
    }
    const buyer = await store.findBuyer(session.buyerPk);
    if (buyer) buyerId = buyer.buyerId;
  } else if (session.apiKey) {
    // legacy path — derive mask from the cookie's plaintext
    initialKey = {
      kid: session.apiKey.slice(0, 16),
      masked: maskApiKey(session.apiKey),
      createdAt: new Date(signedInAt).toISOString(),
      lastUsedAt: null,
    };
  }

  return (
    <div className="surface-buyer min-h-screen bg-bg">
      <MarketplaceNav active="/account" />
      <main className="mx-auto max-w-content px-6 py-6">
        <AccountClient
          buyerId={buyerId}
          email={email}
          tier={tier}
          signedInAt={signedInAt}
          initialKey={initialKey}
          locale={locale}
        />
      </main>
    </div>
  );
}
