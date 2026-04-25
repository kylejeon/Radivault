/**
 * SampleDownloadButton — design-spec §9.
 *
 * 5 visual states:
 *   - default                   (verified study, quota available)
 *   - downloading               (spinner, aria-busy)
 *   - disabled-not-verified     (preview_status != 'verified', tooltip)
 *   - disabled-quota            (today's quota exhausted, tooltip)
 *   - error                     (button reverts; toast surfaces detail)
 *
 * On success: window.open(presigned_url) auto-triggers the browser
 * download. The component reports the new quota state back to the
 * parent so the QuotaIndicator can update without a second round-trip.
 */

"use client";

import { useState } from "react";
import clsx from "clsx";
import toast from "react-hot-toast";
import { getDict, type Locale } from "@/lib/i18n";
import type { QuotaState } from "@/components/preview/QuotaIndicator";

export type SampleDownloadButtonProps = {
  studyUid: string;
  /** preview_status from the study row. Only 'verified' enables download. */
  previewStatus: "verified" | "pending" | "phi_detected" | "not_applicable";
  /** Today's quota — used to render the disabled-quota state. */
  quota?: QuotaState | null;
  /** Called after a successful or failed attempt so the parent can update
   *  the QuotaIndicator and surface error state. */
  onQuotaUpdate?: (next: QuotaState) => void;
  locale?: Locale;
  className?: string;
};

type Phase = "idle" | "downloading";

type SampleDownloadResponse = {
  presigned_url: string;
  expires_at: string;
  instance_uid: string;
  study_uid: string;
  size_bytes: number;
  quota_after?: {
    used: number;
    limit: number;
    resets_at: string;
  };
};

export function SampleDownloadButton({
  studyUid,
  previewStatus,
  quota,
  onQuotaUpdate,
  locale = "en",
  className,
}: SampleDownloadButtonProps) {
  const dict = getDict(locale);
  const [phase, setPhase] = useState<Phase>("idle");

  const verified = previewStatus === "verified";
  const exhausted = !!quota && quota.used >= quota.limit;
  const disabled = !verified || exhausted || phase === "downloading";

  const tooltip = !verified
    ? dict.sampleDownload.tooltipNotVerified
    : exhausted
      ? dict.sampleDownload.tooltipQuotaExceeded
      : undefined;

  async function onClick() {
    if (disabled) return;
    setPhase("downloading");
    try {
      const res = await fetch(
        `/api/studies/${encodeURIComponent(studyUid)}/sample-download`,
        { method: "POST" },
      );
      if (res.status === 429) {
        toast.error(dict.sampleDownload.toastQuotaExceeded);
        // Mark quota as exhausted optimistically.
        if (onQuotaUpdate && quota) {
          onQuotaUpdate({ ...quota, used: quota.limit });
        }
        return;
      }
      if (!res.ok) {
        toast.error(dict.sampleDownload.toastFailed);
        return;
      }
      const body = (await res.json()) as SampleDownloadResponse;
      // Optimistic quota bump (before the parent refreshes).
      if (body.quota_after && onQuotaUpdate) {
        onQuotaUpdate({
          used: body.quota_after.used,
          limit: body.quota_after.limit,
          resetsAtIso: body.quota_after.resets_at,
        });
      }
      toast.success(dict.sampleDownload.toastStarted);
      // Trigger the browser download. window.open is friendlier than
      // synthesising an <a download> because it avoids transient DOM
      // mutation on a page that may unmount mid-flight.
      if (typeof window !== "undefined") {
        window.open(body.presigned_url, "_blank", "noopener,noreferrer");
      }
    } catch (err) {
      toast.error(dict.sampleDownload.toastFailed);
      // Surface the error in dev console for debugging.
      // eslint-disable-next-line no-console
      console.error("sample-download failed", err);
    } finally {
      setPhase("idle");
    }
  }

  const baseCls =
    "inline-flex w-full items-center justify-center gap-2 rounded-md " +
    "px-4 py-3 text-sm font-medium transition-colors " +
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700 focus-visible:ring-offset-2 " +
    "disabled:cursor-not-allowed";
  const enabledCls = "bg-primary-600 text-white hover:bg-primary-700";
  const disabledCls = "bg-bg-muted text-text-muted opacity-60";

  return (
    <button
      type="button"
      data-testid="sample-download-button"
      data-state={
        !verified
          ? "disabled-not-verified"
          : exhausted
            ? "disabled-quota"
            : phase === "downloading"
              ? "downloading"
              : "default"
      }
      onClick={onClick}
      disabled={disabled}
      aria-disabled={disabled || undefined}
      aria-busy={phase === "downloading" || undefined}
      title={tooltip}
      className={clsx(
        baseCls,
        disabled ? disabledCls : enabledCls,
        className,
      )}
    >
      {phase === "downloading" ? (
        <>
          <span
            aria-hidden
            className="inline-block size-4 animate-spin rounded-full border-2 border-current border-t-transparent"
          />
          <span>{dict.sampleDownload.ctaPreparing}</span>
        </>
      ) : (
        <>
          <span aria-hidden>↓</span>
          <span>{dict.sampleDownload.cta}</span>
        </>
      )}
    </button>
  );
}
