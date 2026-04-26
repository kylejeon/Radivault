/**
 * <TrustBar> + <PIPATrustNote> — buyer-search-v3 FR-V3-UI-7.
 *
 * - TrustBar: amber pill in the top nav, always visible. "PIPA §28-8 ·
 *   정통망법 · KCD-8".
 * - PIPATrustNote: amber-bordered footer note declaring the production
 *   policy for exact-age + exact-date exposure. Both languages always
 *   rendered (locale-toggle CSS hides the inactive one).
 */

export function TrustBar({ locale = "en" }: { locale?: "ko" | "en" }) {
  return (
    <span className="rv-trust-bar" data-testid="v3-trust-bar">
      <span className="rv-trust-bar__dot" />
      {locale === "ko"
        ? "개인정보보호법 §28-8 · 정통망법 · KCD-8"
        : "PIPA §28-8 · 정통망법 · KCD-8"}
    </span>
  );
}

export function PIPATrustNote({ locale = "en" }: { locale?: "ko" | "en" }) {
  return (
    <div className="rv-pipa-note" data-testid="v3-pipa-note">
      <strong>{locale === "ko" ? "운영 정책" : "Production policy"}</strong>
      {locale === "ko"
        ? "정확 환자 나이(세) 와 촬영일(YYYY-MM-DD) 은 검증된 buyer 에게만 노출됩니다. 개인정보보호법 §28-8 가명정보 처리 동의, IRB 승인, 쿼리별 감사 로그로 buyer별 접근이 통제됩니다. 집단 재식별 위험은 fulfillment 시 병원별 k-익명성 ≥ 5 코호트 기준으로 완화됩니다."
        : "Exact patient age (years) and exam date (YYYY-MM-DD) are surfaced to verified buyers. Per-buyer access controlled via signed PIPA §28-8 data use agreement, IRB approval, and per-query audit log. Aggregate re-identification risk is mitigated by hospital-level k-anonymity ≥ 5 cohort enforcement at fulfillment time."}
    </div>
  );
}
