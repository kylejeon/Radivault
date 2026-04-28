"use client";

/**
 * <ComplianceCollapse> — collapsible footer block on the study-detail page
 * that wraps the DeID stepper + audit chain provenance (mockup
 * `.compliance-collapse`).
 *
 * Demoted from a sticky right-rail in v2 to a default-collapsed footer in v3
 * (mockup index.html v2→v3 axis A3 — "buyer doesn't need De-ID detail to
 * decide; promote post-purchase only"). Buyers can still click the head to
 * expand and inspect the full chain.
 *
 * Composes:
 *   - <DeIDStepper>  — left column when expanded
 *   - <AuditInfo>    — right column (PIPA consent + chain hash + IRB)
 *
 * Audit values surface "—" for fields not yet wired (IRB, anchor hash, chain
 * status) — backend audit chain integration is a separate dev-spec.
 */

import { useState } from "react";
import { DeIDStepper, type DeIDStage } from "./DeIDStepper";
import type { Locale } from "@/lib/i18n";

export type ComplianceCollapseProps = {
  /** Per-stage state passed through to <DeIDStepper>. */
  deidStages?: DeIDStage[];
  rulesetVersion?: string | null;
  runAt?: string | null;
  /** Audit chain values (all optional). */
  hospitalIrb?: string | null;
  consentType?: string | null;
  ingestedAt?: string | null;
  anchorHash?: string | null;
  chainStatus?: "continuous" | "broken" | null;
  chainEventCount?: number | null;
  wormRetentionYears?: number | null;
  /** Default expanded? Mockup default is collapsed (false). */
  defaultOpen?: boolean;
  locale?: Locale;
};

export function ComplianceCollapse({
  deidStages,
  rulesetVersion,
  runAt,
  hospitalIrb,
  consentType,
  ingestedAt,
  anchorHash,
  chainStatus,
  chainEventCount,
  wormRetentionYears,
  defaultOpen = false,
  locale = "en",
}: ComplianceCollapseProps) {
  const [open, setOpen] = useState(defaultOpen);

  const t =
    locale === "ko"
      ? {
          head: "컴플라이언스 · 감사",
          headHint: "행정 정보 — 구매 후 확인",
          verified: "5 / 5 익명화 단계 검증",
          auditTitle: "PIPA 동의 출처 · 감사 체인",
          irb: "병원 IRB",
          consent: "동의 유형",
          ingest: "수집 시각",
          anchor: "앵커 해시",
          chain: "체인 상태",
          chainContinuous: (n: number) => `✓ 연속 · ${n.toLocaleString()}건 이벤트`,
          chainBroken: "체인 끊김",
          worm: "WORM 보존",
          wormY: (y: number) => `${y}년 (PIPA 기준)`,
          fullLog:
            "전체 감사 로그 · 체인 증명은 구매 후 Account → 감사 로그 에서 확인 가능.",
        }
      : {
          head: "Compliance & audit",
          headHint: "administrative — view post-purchase",
          verified: "5 / 5 De-ID stages verified",
          auditTitle: "PIPA consent provenance & audit chain",
          irb: "Hospital IRB",
          consent: "Consent type",
          ingest: "Ingest at",
          anchor: "Anchor hash",
          chain: "Chain status",
          chainContinuous: (n: number) =>
            `✓ continuous · ${n.toLocaleString()} events`,
          chainBroken: "broken",
          worm: "WORM retention",
          wormY: (y: number) => `${y}y per PIPA`,
          fullLog:
            "Full audit log + chain proof available post-purchase via Account → Audit log.",
        };

  return (
    <section
      className={"rv-compliance-collapse" + (open ? " is-open" : "")}
      data-testid="compliance-collapse"
      data-state={open ? "open" : "closed"}
    >
      <button
        type="button"
        className="rv-compliance-collapse__head"
        data-testid="compliance-collapse-head"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 10,
            flexWrap: "wrap",
          }}
        >
          <span
            className="rv-trust-bar"
            style={{
              background: "rgba(20,184,166,0.15)",
              border: "1px solid rgba(20,184,166,0.4)",
              color: "var(--rv-teal-700)",
            }}
          >
            <span
              className="rv-trust-bar__dot"
              style={{ background: "var(--rv-teal-500)" }}
            />
            <span>{t.verified}</span>
          </span>
          <span>{t.head}</span>
          <span
            style={{
              fontSize: 11,
              color: "var(--rv-stone-500)",
              fontWeight: 500,
            }}
          >
            {t.headHint}
          </span>
        </span>
        <span className="rv-compliance-collapse__head__chev">▾</span>
      </button>

      <div className="rv-compliance-collapse__body">
        <DeIDStepper
          stages={deidStages}
          rulesetVersion={rulesetVersion ?? null}
          runAt={runAt ?? null}
          locale={locale}
        />

        <div className="rv-audit-info" data-testid="compliance-audit-info">
          <h4>{t.auditTitle}</h4>
          <dl>
            <AuditRow k={t.irb} v={hospitalIrb} testid="audit-irb" />
            <AuditRow k={t.consent} v={consentType} testid="audit-consent" />
            <AuditRow k={t.ingest} v={ingestedAt} testid="audit-ingest" />
            <AuditRow k={t.anchor} v={anchorHash} testid="audit-anchor-hash" />
            <AuditRow
              k={t.chain}
              v={
                chainStatus === "continuous" && chainEventCount != null
                  ? t.chainContinuous(chainEventCount)
                  : chainStatus === "broken"
                    ? t.chainBroken
                    : null
              }
              good={chainStatus === "continuous"}
              testid="audit-chain"
            />
            <AuditRow
              k={t.worm}
              v={wormRetentionYears != null ? t.wormY(wormRetentionYears) : null}
              testid="audit-worm"
            />
          </dl>
          <div
            style={{
              marginTop: 12,
              paddingTop: 10,
              borderTop: "1px dashed var(--rv-stone-200)",
              fontSize: 11,
              color: "var(--rv-stone-500)",
            }}
          >
            {t.fullLog}
          </div>
        </div>
      </div>
    </section>
  );
}

function AuditRow({
  k,
  v,
  good,
  testid,
}: {
  k: string;
  v: string | null | undefined;
  good?: boolean;
  testid: string;
}) {
  const missing = v == null || v === "";
  return (
    <>
      <dt>{k}</dt>
      <dd
        className={missing ? "dd--missing" : undefined}
        data-testid={testid}
        style={{
          color: missing
            ? "var(--rv-stone-400)"
            : good
              ? "var(--rv-success-fg)"
              : undefined,
        }}
      >
        {missing ? "—" : v}
      </dd>
    </>
  );
}
