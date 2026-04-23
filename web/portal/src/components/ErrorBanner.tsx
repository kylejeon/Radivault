import clsx from "clsx";
import { resolveError } from "@/lib/errors";

/**
 * ErrorBanner — consumes a BFF error code and renders the design-spec §7
 * friendly copy with a "Copy request id" affordance.
 */
export function ErrorBanner({
  code,
  requestId,
  detail,
}: {
  code?: string;
  requestId?: string;
  detail?: string;
}) {
  const msg = resolveError(code);
  const toneClass = {
    auth: "bg-yellow-50 text-yellow-900 border-yellow-300",
    user: "bg-orange-50 text-orange-900 border-orange-300",
    system: "bg-red-50 text-red-900 border-red-300",
    rate: "bg-blue-50 text-blue-900 border-blue-300",
    offline: "bg-slate-50 text-slate-900 border-slate-300",
  }[msg.variant];
  return (
    <div role="alert" className={clsx("rounded-md border px-4 py-3 text-sm", toneClass)}>
      <div className="font-semibold">{msg.title}</div>
      <div className="mt-0.5">{msg.hint}</div>
      {(detail || requestId) && (
        <div className="mt-2 font-mono text-xs opacity-70">
          {detail ? <span>{detail}</span> : null}
          {requestId ? <span> · req: {requestId}</span> : null}
        </div>
      )}
    </div>
  );
}
