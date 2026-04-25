/**
 * FooterEn — design-spec-portal-redesign §5.7 ({#footer-en-v1}).
 *
 * 6-column Stripe/Vercel layout for the English homepage. KR equivalent
 * lives in `FooterKr.tsx` (different column count + Korean B2B legal
 * block per FR-HP-9).
 *
 * All link `href`s point to home anchors today (v0.1 stub) — replacing
 * them is a content task, not a structural one.
 */

import Link from "next/link";
import { getDict } from "@/lib/i18n";
import { LangToggle } from "./LangToggle";

const COLUMNS = [
  "product",
  "solutions",
  "developers",
  "resources",
  "company",
  "legal",
] as const;

export function FooterEn() {
  const dict = getDict("en");

  return (
    <footer
      data-testid="footer-en"
      className="border-t border-border bg-bg-muted"
    >
      <nav
        aria-label={dict.nav.footerNav}
        className="mx-auto max-w-content px-6 py-12"
      >
        <div className="mb-10 flex items-center gap-2">
          <span
            aria-hidden
            className="inline-flex size-7 items-center justify-center rounded-md bg-primary-600 text-white"
          >
            ◆
          </span>
          <span className="text-lg font-semibold text-text-strong">
            RadiVault
          </span>
        </div>
        <div className="grid grid-cols-2 gap-8 tablet:grid-cols-3 desktop:grid-cols-6">
          {COLUMNS.map((key) => {
            const col = dict.footer.columns[key];
            return (
              <div key={key}>
                <h4 className="text-sm font-semibold text-text">{col.title}</h4>
                <ul className="mt-3 space-y-2">
                  {col.links.map((link) => (
                    <li key={link}>
                      <Link
                        href="/"
                        className="text-sm text-text-muted hover:text-primary-600"
                      >
                        {link}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
        <div className="mt-12 flex flex-col items-start justify-between gap-4 border-t border-border pt-6 tablet:flex-row tablet:items-center">
          <span className="text-xs text-text-muted">{dict.footer.rights}</span>
          <div className="flex items-center gap-4">
            <LangToggle locale="en" />
            <span className="text-text-muted" aria-hidden>
              ·
            </span>
            <span className="flex items-center gap-3 text-text-muted">
              <a href="https://twitter.com" aria-label={dict.footer.socialTwitter} className="hover:text-text">
                𝕏
              </a>
              <a href="https://linkedin.com" aria-label={dict.footer.socialLinkedIn} className="hover:text-text">
                in
              </a>
              <a href="https://github.com" aria-label={dict.footer.socialGithub} className="hover:text-text">
                ⌂
              </a>
            </span>
          </div>
        </div>
      </nav>
    </footer>
  );
}
