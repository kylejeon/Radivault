/**
 * HospitalHeader — design-spec §17 / §18 wordmark + KR top nav.
 *
 * Top nav per FR-HO-9 (≤ 4 chars per Korean label): 대시 / 주문 / 감사
 * / 설정 / 로그아웃. /hospital/orders + /hospital/settings stay v0.1
 * stubs but the nav slots are reserved so users build the muscle memory
 * before v0.1.1.
 */

import Link from "next/link";
import { getDict } from "@/lib/i18n";

export function HospitalHeader({ hospitalId }: { hospitalId: string }) {
  const dict = getDict("ko");
  return (
    <header className="border-b border-border bg-white">
      <div className="mx-auto flex max-w-content items-center justify-between gap-6 px-6 py-4 lang-ko">
        <div className="flex items-center gap-3">
          <span
            aria-hidden
            className="inline-flex size-7 items-center justify-center rounded-md bg-teal-600 text-white"
          >
            ◆
          </span>
          <div>
            <div className="text-sm font-semibold text-text-strong">
              {dict.hospital.nav.wordmark}
            </div>
            <div className="text-xs text-text-muted">
              병원 코드: <code className="font-mono">{hospitalId}</code>
            </div>
          </div>
        </div>
        <nav
          aria-label="병원 콘솔 메뉴"
          className="hidden items-center gap-4 text-sm text-text-muted md:flex"
        >
          <Link href="/hospital" className="hover:text-teal-700">
            {dict.hospital.nav.dashboard}
          </Link>
          <Link href="/hospital/orders" className="hover:text-teal-700">
            {dict.hospital.nav.orders}
          </Link>
          <Link href="/hospital/audit" className="hover:text-teal-700">
            {dict.hospital.nav.audit}
          </Link>
          <Link href="/hospital/quota" className="hover:text-teal-700">
            {dict.hospital.nav.settings}
          </Link>
        </nav>
        <form action="/api/hospital/session/delete" method="post">
          <button
            type="submit"
            className="rounded-md border border-border px-3 py-1.5 text-sm text-text-muted hover:bg-bg-muted"
          >
            {dict.hospital.nav.signOut}
          </button>
        </form>
      </div>
    </header>
  );
}
