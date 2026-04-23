import Link from "next/link";
import { TopNav } from "@/components/TopNav";
import { getBuyerSession } from "@/lib/session";

export default async function DocsPage() {
  const session = await getBuyerSession().catch(() => ({}) as Awaited<ReturnType<typeof getBuyerSession>>);
  return (
    <div className="surface-buyer min-h-screen">
      <TopNav active="/docs" signedIn={Boolean(session?.apiKey)} />
      <main className="mx-auto max-w-3xl px-6 py-10 prose">
        <h1>Docs</h1>
        <p>
          Full API quickstart and order-flow guide live in the marketing
          repo. The short version:
        </p>
        <ol>
          <li>Obtain an <code>rv_live_</code> key from sales.</li>
          <li><Link href="/signin">Sign in</Link>.</li>
          <li>Browse <Link href="/search">Search</Link> to build a cohort.</li>
          <li>Review → Confirm. Track progress under <Link href="/orders">Orders</Link>.</li>
          <li>When phase = ready, fetch presigned URLs from the Downloads tab.</li>
        </ol>
        <h2>Contacts</h2>
        <ul>
          <li>
            Sales: <a href="mailto:sales@radivault.io">sales@radivault.io</a>
          </li>
          <li>
            Support: <a href="mailto:support@radivault.io">support@radivault.io</a>
          </li>
        </ul>
      </main>
    </div>
  );
}
