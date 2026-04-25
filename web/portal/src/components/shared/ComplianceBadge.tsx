/**
 * ComplianceBadge — design-spec-portal-redesign §5.10 ({#compliance-badge-v1}).
 *
 * Single source of truth for the compliance vocabulary. Any other file that
 * tries to render "PIPA / SOC 2 / ISO 27001 / HIPAA" labels by hand is
 * caught by `scripts/check_compliance_voice.sh` (FR-NFR-7) and the build
 * will fail in CI.
 *
 * Variants come from FR-SH-3:
 *   - `pipa`     — "compliant" (success)
 *   - `soc2`     — "in preparation" (warning)
 *   - `iso27001` — "aligned" (info)
 *   - `hipaa`    — "de-identification" (info)
 *
 * Reduced motion handled by globals.css (no animation here).
 */

import clsx from "clsx";
import type { Locale } from "@/lib/i18n";
import { getDict } from "@/lib/i18n";

export type ComplianceVariant = "pipa" | "soc2" | "iso27001" | "hipaa";

const STATUS_TONE: Record<ComplianceVariant, "success" | "warning" | "info"> = {
  pipa: "success",
  soc2: "warning",
  iso27001: "info",
  hipaa: "info",
};

const TONE_CLASSES: Record<"success" | "warning" | "info", string> = {
  success: "bg-status-success-bg text-status-success-fg",
  warning: "bg-status-warning-bg text-status-warning-fg",
  info: "bg-status-info-bg text-status-info-fg",
};

export function ComplianceBadge({
  variant,
  locale,
  className,
}: {
  variant: ComplianceVariant;
  locale: Locale;
  className?: string;
}) {
  const dict = getDict(locale);
  const item = dict.trustBar[variant];
  const tone = STATUS_TONE[variant];

  return (
    <span
      data-testid={`compliance-badge-${variant}`}
      className={clsx(
        "inline-flex items-center gap-2 rounded-pill px-3 py-1 text-xs font-semibold",
        TONE_CLASSES[tone],
        className,
      )}
    >
      <Dot tone={tone} />
      <span>
        {item.title} {item.status}
      </span>
    </span>
  );
}

function Dot({ tone }: { tone: "success" | "warning" | "info" }) {
  const color =
    tone === "success" ? "#047857" : tone === "warning" ? "#b45309" : "#1d4ed8";
  return (
    <span
      aria-hidden
      className="inline-block size-2 rounded-pill"
      style={{ background: color }}
    />
  );
}
