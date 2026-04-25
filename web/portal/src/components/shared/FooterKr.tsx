/**
 * FooterKr — design-spec-portal-redesign §5.8 ({#footer-kr-v1}).
 *
 * Korean B2B legal block (FR-HP-9). Required fields:
 *   - 대표자 / 사업자등록번호 / 통신판매업 신고 / 주소 / 고객센터 / 이메일
 *   - 개인정보처리방침 anchor
 *   - KISMS-P / ISO 27001 / PIPA badges
 *
 * Values are sourced from `NEXT_PUBLIC_LEGAL_*` env vars. When those are
 * unset they fall back to `[TBD]`. The build-guard
 * `scripts/check_tbd_in_build.sh` (FR-HP-9) refuses production builds
 * that ship `[TBD]` strings.
 */

import Link from "next/link";
import { getDict } from "@/lib/i18n";
import { ComplianceBadge } from "./ComplianceBadge";
import { LangToggle } from "./LangToggle";

const KO_COLUMNS = ["product", "solutions", "company", "legal"] as const;

const TBD = "[TBD]";

function legalEnv(key: string): string {
  // Read at build time — keys exposed via NEXT_PUBLIC_* are inlined.
  if (typeof process === "undefined") return TBD;
  const value = process.env[`NEXT_PUBLIC_LEGAL_${key}`];
  return value && value.length > 0 ? value : TBD;
}

export function FooterKr() {
  const dict = getDict("ko");
  const legal = {
    representative: legalEnv("REPRESENTATIVE") || "Kyle Jeon",
    bizNumber: legalEnv("BIZ_NUMBER"),
    mailOrderNumber: legalEnv("MAIL_ORDER_NUMBER"),
    address: legalEnv("ADDRESS"),
    customerCenter: legalEnv("CUSTOMER_CENTER"),
    email: legalEnv("EMAIL") || "sales@radivault.io",
  };

  return (
    <footer
      data-testid="footer-kr"
      className="border-t border-border bg-bg-muted lang-ko"
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
        <div className="grid grid-cols-2 gap-8 tablet:grid-cols-4">
          {KO_COLUMNS.map((key) => {
            const col = dict.footer.columns[key];
            return (
              <div key={key}>
                <h4 className="text-sm font-semibold text-text">{col.title}</h4>
                <ul className="mt-3 space-y-2">
                  {col.links.map((link) => (
                    <li key={link}>
                      <Link
                        href="/ko"
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

        {/* Korean B2B legal block — FR-HP-9. Each field renders even when
            the value is `[TBD]` so the production build-guard fires. */}
        <section
          className="mt-10 border-t border-border pt-6 text-xs leading-relaxed text-text-muted"
          data-testid="footer-kr-legal"
        >
          <div className="font-semibold text-text">RadiVault Inc.</div>
          <div className="mt-2 grid gap-x-6 gap-y-1 tablet:grid-cols-2">
            <span>대표자: {legal.representative}</span>
            <span>사업자등록번호: {legal.bizNumber}</span>
            <span>통신판매업 신고: {legal.mailOrderNumber}</span>
            <span>주소: {legal.address}</span>
            <span>고객센터: {legal.customerCenter}</span>
            <span>이메일: {legal.email}</span>
          </div>
          <div className="mt-4">
            <Link
              href="/ko/legal/privacy"
              className="text-sm font-medium text-primary-600 hover:text-primary-700"
            >
              개인정보처리방침
            </Link>
          </div>
        </section>

        <div className="mt-8 flex flex-wrap gap-3">
          <ComplianceBadge variant="pipa" locale="ko" />
          <ComplianceBadge variant="iso27001" locale="ko" />
          <ComplianceBadge variant="hipaa" locale="ko" />
          <ComplianceBadge variant="soc2" locale="ko" />
        </div>

        <div className="mt-8 flex flex-col items-start justify-between gap-4 border-t border-border pt-6 tablet:flex-row tablet:items-center">
          <span className="text-xs text-text-muted">{dict.footer.rights}</span>
          <LangToggle locale="ko" />
        </div>
      </nav>
    </footer>
  );
}
