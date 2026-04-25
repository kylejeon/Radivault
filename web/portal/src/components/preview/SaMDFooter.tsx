/**
 * SaMDFooter — design-spec-buyer-browse-preview §8.
 *
 * Sticky-bottom medical-device disclaimer for the viewer page. Always
 * visible (FR-PREVIEW-4 forbids dismiss). Renders the EN/KR string from
 * ``samd.disclaimer`` plus the TCIA CC-BY attribution.
 *
 * Visual contract: warning bg (#fffbeb), warning text (#b45309), 12px
 * font-medium, border-top 1px (#92400e). Color contrast 4.74:1 ≥ WCAG AA.
 */

import { getDict, type Locale } from "@/lib/i18n";

export type SaMDFooterProps = {
  locale?: Locale;
  className?: string;
};

export function SaMDFooter({ locale = "en", className }: SaMDFooterProps) {
  const dict = getDict(locale);
  return (
    <footer
      data-testid="samd-disclaimer"
      role="contentinfo"
      aria-label="Medical device disclaimer"
      // Tailwind palette references the design tokens already in
      // tailwind.config.ts; the warning bg / text /border colors are the
      // closest-matching status palette swatches (amber-50 / amber-700 /
      // amber-800) — same hex values cited in design-spec §4.1.
      className={
        "sticky bottom-0 z-30 w-full border-t border-amber-800 bg-amber-50 px-6 py-3 " +
        "text-xs font-medium text-amber-700 " +
        "[word-break:keep-all] " +
        (className ?? "")
      }
      style={{
        // Belt-and-braces — explicit hex so the design-spec colour contract
        // holds even if the Tailwind purge picks a slightly different
        // shade alias.
        backgroundColor: "#fffbeb",
        borderTopColor: "#92400e",
        color: "#b45309",
      }}
    >
      <div className="flex flex-col gap-1 text-center md:flex-row md:items-start md:justify-between md:text-left">
        <p className="max-w-prose">
          <span aria-hidden className="mr-1">⚠</span>
          {dict.samd.disclaimer}
        </p>
        <p className="text-[11px] opacity-80">{dict.samd.tciaAttribution}</p>
      </div>
    </footer>
  );
}
