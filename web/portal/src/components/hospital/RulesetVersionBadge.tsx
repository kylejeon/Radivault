/**
 * RulesetVersionBadge {#ruleset-badge-v1} — design-spec §17.4.
 *
 * Three-line stacked badge for the de-id ruleset, salt rotation, and
 * pixel engine versions. The salt-version line flips to "outdated"
 * (amber) if the next rotate date has already passed.
 */

"use client";

import Link from "next/link";
import clsx from "clsx";
import { getDict } from "@/lib/i18n";
import { formatKstDate } from "./format";

export type RulesetVersionData = {
  ruleset_version: string | null;
  salt_version: string | null;
  salt_rotate_at: string | null;
  pixel_engine_version: string | null;
};

function isOutdated(rotateAt: string | null): boolean {
  if (!rotateAt) return false;
  const t = new Date(rotateAt).getTime();
  if (!Number.isFinite(t)) return false;
  return t < Date.now();
}

export function RulesetVersionBadge({
  data,
  loading = false,
  error = false,
  testId = "ruleset-version-badge",
}: {
  data: RulesetVersionData | null;
  loading?: boolean;
  error?: boolean;
  testId?: string;
}) {
  const dict = getDict("ko");

  if (loading) {
    return (
      <div data-testid={testId} data-state="loading" className="flex flex-col gap-1.5">
        <div className="skeleton h-3 w-40" />
        <div className="skeleton h-3 w-36" />
        <div className="skeleton h-3 w-32" />
      </div>
    );
  }
  if (error || !data) {
    return (
      <div
        data-testid={testId}
        data-state="error"
        className="text-sm text-text-muted"
      >
        {dict.hospital.tile.versionFetchFailed}
      </div>
    );
  }

  const outdated = isOutdated(data.salt_rotate_at);
  const variant = outdated ? "outdated" : "current";

  return (
    <Link
      href="/hospital/quota"
      data-testid={testId}
      data-variant={variant}
      className="block rounded-md border border-transparent p-1 hover:border-border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-300"
    >
      <div className="flex flex-col gap-1 text-sm">
        <div className="flex items-center justify-between">
          <span className="text-text-muted">{dict.hospital.tile.ruleset_label}</span>
          <code className="font-mono text-text">{data.ruleset_version ?? "—"}</code>
        </div>
        <div
          className={clsx(
            "flex items-center justify-between",
            outdated && "text-amber-700",
          )}
        >
          <span className="text-text-muted">{dict.hospital.tile.salt_label}</span>
          <code className="font-mono">{data.salt_version ?? "—"}</code>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-text-muted">{dict.hospital.tile.pixelEngine_label}</span>
          <code className="font-mono text-text">{data.pixel_engine_version ?? "—"}</code>
        </div>
        <div className="mt-1 text-[11px] text-text-muted">
          {dict.hospital.tile.saltRotateNext}: {formatKstDate(data.salt_rotate_at)}
        </div>
      </div>
    </Link>
  );
}
