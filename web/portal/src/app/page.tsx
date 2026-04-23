import Link from "next/link";
import { TopNav } from "@/components/TopNav";
import { getBuyerSession } from "@/lib/session";

/**
 * A-1 Home / Hero (design-spec §5, FR-A-8..FR-A-10).
 *
 * Public page. Three proof tiles are static for v0.1 — the live `/v1/search/facets`
 * pull is an optional upgrade when BFF can reach the metadata-index at
 * render time.
 */
export default async function Home() {
  const session = await getBuyerSession().catch(() => ({}) as Awaited<ReturnType<typeof getBuyerSession>>);
  const signedIn = Boolean(session?.apiKey);

  return (
    <div className="surface-buyer">
      <TopNav active="/" signedIn={signedIn} />
      <main className="mx-auto max-w-7xl px-6 py-20">
        <section className="flex flex-col items-start gap-6">
          <span className="rounded-full bg-primary-soft px-3 py-1 text-xs font-semibold uppercase tracking-wide text-primary">
            K-MedData · v0.1
          </span>
          <h1 className="max-w-3xl text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">
            Korea&rsquo;s medical imaging data,{" "}
            <span className="text-primary">compliantly delivered</span> to the
            world&rsquo;s AI.
          </h1>
          <p className="max-w-2xl text-lg text-ink-muted">
            Search de-identified Korean radiology datasets by modality, body
            part, and age. Order a cohort. Download presigned URLs with
            audit-chained provenance. All without PHI leaving Korea.
          </p>
          <div className="flex gap-3">
            <Link
              href={signedIn ? "/search" : "/signin"}
              className="rounded-md bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground"
            >
              {signedIn ? "Go to search" : "Sign in with API key"}
            </Link>
            <Link
              href="/docs"
              className="rounded-md border border-surface-border px-5 py-2.5 text-sm font-semibold text-ink-muted hover:bg-white"
            >
              Read API docs
            </Link>
          </div>
        </section>

        <section className="mt-16 grid grid-cols-1 gap-4 md:grid-cols-3">
          <ProofTile
            value="—"
            label="Studies indexed"
            caption="Live via /v1/search/facets"
          />
          <ProofTile
            value="—"
            label="Hospitals contributing"
            caption="Pilot partners (KR)"
          />
          <ProofTile
            value="< 48h"
            label="Designed turnaround p95"
            caption="From order to presigned URL"
          />
        </section>

        <footer className="mt-24 border-t border-surface-border pt-6 text-xs text-ink-subtle">
          Data powered by TCIA CC-BY where applicable. We use essential cookies for
          session. No tracking.
        </footer>
      </main>
    </div>
  );
}

function ProofTile({
  value,
  label,
  caption,
}: {
  value: string;
  label: string;
  caption: string;
}) {
  return (
    <div className="card p-6">
      <div className="text-3xl font-semibold tabular-nums text-ink">{value}</div>
      <div className="mt-2 text-sm font-medium text-ink">{label}</div>
      <div className="mt-0.5 text-xs text-ink-subtle">{caption}</div>
    </div>
  );
}
