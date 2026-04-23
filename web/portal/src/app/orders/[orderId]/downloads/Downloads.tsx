"use client";

import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";

type DownloadFile = {
  object_key: string;
  bytes: number;
  sha256: string;
  url: string;
};

type DownloadItem = {
  pseudo_study_uid: string;
  files: DownloadFile[];
};

type Batch = {
  order_id: string;
  ttl_seconds: number;
  expires_at: string;
  items: DownloadItem[];
  total_bytes: number;
};

export function Downloads({ orderId }: { orderId: string }) {
  const [batch, setBatch] = useState<Batch | null>(null);
  const [error, setError] = useState<{ code?: string; detail?: string; requestId?: string } | null>(
    null,
  );
  const [tab, setTab] = useState<"browser" | "curl" | "python">("browser");

  useEffect(() => {
    void (async () => {
      try {
        const res = await fetch(`/api/orders/${orderId}/download-urls`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          setError({ code: body?.error, detail: body?.detail, requestId: body?.request_id });
          return;
        }
        setBatch(await res.json());
      } catch (err) {
        setError({ code: "ERR_UPSTREAM_UNAVAILABLE", detail: String(err) });
      }
    })();
  }, [orderId]);

  if (error) return <ErrorBanner {...error} />;
  if (!batch) {
    return (
      <div className="flex flex-col gap-2">
        <div className="card h-10 animate-pulse" />
        <div className="card h-40 animate-pulse" />
      </div>
    );
  }

  const filesFlat = batch.items.flatMap((i) => i.files);
  const expiresIn = Math.max(0, new Date(batch.expires_at).getTime() - Date.now());
  const hours = Math.floor(expiresIn / 3_600_000);
  const minutes = Math.floor((expiresIn % 3_600_000) / 60_000);

  return (
    <div className="flex flex-col gap-5">
      <header className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold">Downloads</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Order <span className="font-mono">{batch.order_id.slice(-8)}</span> ·{" "}
            {filesFlat.length.toLocaleString()} files ·{" "}
            {(batch.total_bytes / (1024 * 1024)).toFixed(1)} MB
          </p>
        </div>
        <div className="text-right text-sm">
          <div className="text-ink-muted">Expires in</div>
          <div className="font-semibold tabular-nums">
            {hours}h {String(minutes).padStart(2, "0")}m
          </div>
        </div>
      </header>

      <div className="flex gap-1 border-b border-surface-border">
        {(["browser", "curl", "python"] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={
              "px-4 py-2 text-sm " +
              (tab === t
                ? "border-b-2 border-primary text-primary"
                : "text-ink-muted hover:text-ink")
            }
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "browser" ? <BrowserList files={filesFlat} /> : null}
      {tab === "curl" ? <CurlSnippet files={filesFlat} /> : null}
      {tab === "python" ? <PythonSnippet orderId={batch.order_id} /> : null}
    </div>
  );
}

function BrowserList({ files }: { files: DownloadFile[] }) {
  return (
    <div className="card divide-y divide-surface-border">
      {files.map((f, i) => (
        <div key={`${f.object_key}-${i}`} className="flex items-center justify-between px-4 py-2">
          <div className="min-w-0 flex-1 truncate font-mono text-xs text-ink">
            {f.object_key}
          </div>
          <div className="flex items-center gap-4 text-xs text-ink-subtle">
            <span>{(f.bytes / 1024).toFixed(1)} KB</span>
            <code>…{f.sha256.slice(-8)}</code>
            <a
              href={f.url}
              className="rounded bg-primary px-2 py-1 text-primary-foreground"
              rel="noreferrer"
            >
              Download
            </a>
          </div>
        </div>
      ))}
    </div>
  );
}

function CurlSnippet({ files }: { files: DownloadFile[] }) {
  const snippet = files
    .slice(0, 5)
    .map((f) => `curl -o "$(basename '${f.object_key}')" "${f.url}"`)
    .join("\n");
  return (
    <pre className="card max-h-80 overflow-auto bg-slate-900 p-4 text-xs text-slate-100">
{snippet || "# No files in batch."}
{files.length > 5 ? `\n# ...and ${files.length - 5} more` : ""}
    </pre>
  );
}

function PythonSnippet({ orderId }: { orderId: string }) {
  const snippet = `import os, requests
r = requests.post(
    f"{os.environ['RV_BASE']}/v1/orders/${orderId}/download-urls",
    headers={"Authorization": f"Bearer {os.environ['RV_KEY']}"},
    json={"ttl_seconds": 3600},
).json()
for item in r["items"]:
    for f in item["files"]:
        open(os.path.basename(f["object_key"]), "wb").write(
            requests.get(f["url"]).content
        )
`;
  return (
    <pre className="card max-h-80 overflow-auto bg-slate-900 p-4 text-xs text-slate-100">
      {snippet}
    </pre>
  );
}
