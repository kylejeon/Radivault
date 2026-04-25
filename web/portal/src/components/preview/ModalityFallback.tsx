/**
 * ModalityFallback — design-spec §11.
 *
 * Used in the StudyDetail viewer slot when the study is NOT verified
 * (preview_status != 'verified') OR when the modality is single-frame
 * but no preview asset exists. Renders a centered icon + label so the
 * page layout stays the same as a populated SliceViewer.
 */

import clsx from "clsx";
import Link from "next/link";
import { getDict, type Locale } from "@/lib/i18n";

export type ModalityFallbackVariant =
  | "unavailable-pending"
  | "unavailable-phi"
  | "unavailable-modality"
  | "single-frame";

export type ModalityFallbackProps = {
  variant: ModalityFallbackVariant;
  modality?: string | null;
  locale?: Locale;
  className?: string;
};

const ICON_FOR_VARIANT: Record<ModalityFallbackVariant, string> = {
  "unavailable-pending": "▢",
  "unavailable-phi": "⚠",
  "unavailable-modality": "▢",
  "single-frame": "▤",
};

export function ModalityFallback({
  variant,
  locale = "en",
  className,
}: ModalityFallbackProps) {
  const dict = getDict(locale);
  const title =
    variant === "unavailable-phi"
      ? dict.preview.unavailablePhi
      : variant === "unavailable-modality"
        ? dict.preview.unavailableModality
        : dict.preview.unavailableShort;
  const body =
    variant === "unavailable-pending"
      ? dict.preview.unavailablePending
      : variant === "unavailable-phi"
        ? dict.preview.unavailablePhi
        : variant === "single-frame"
          ? ""
          : dict.preview.unavailableModality;
  const icon = ICON_FOR_VARIANT[variant];

  return (
    <div
      data-testid="modality-fallback"
      data-variant={variant}
      role="region"
      aria-label={dict.preview.unavailableShort}
      className={clsx(
        "flex flex-col items-center justify-center gap-3 rounded-md bg-bg-muted",
        "px-6 py-12 text-center",
        className,
      )}
    >
      <span aria-hidden className="text-5xl text-text-muted">
        {icon}
      </span>
      <h3 className="text-base font-medium text-text">{title}</h3>
      {body ? (
        <p className="max-w-prose text-sm text-text-muted">{body}</p>
      ) : null}
      {variant !== "single-frame" ? (
        <Link
          href="/search"
          className="mt-2 inline-flex rounded-md border border-border-strong px-3 py-1.5 text-sm font-medium text-text hover:bg-bg"
        >
          {dict.preview.browseVerified} →
        </Link>
      ) : null}
    </div>
  );
}
