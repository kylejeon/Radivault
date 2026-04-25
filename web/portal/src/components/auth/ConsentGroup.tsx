"use client";

/**
 * <ConsentGroup> — design-spec-buyer-auth §5.4 {#consent-group-v1}.
 *
 * EN variant: 2 checkboxes (ToS+Privacy required, Marketing optional).
 * KR variant: 4-way PIPA split (collectUse + thirdParty + crossBorder
 * required; marketing optional) + master "전체 동의" with indeterminate
 * state. Per Kyle Q4: master ticks REQUIRED ONLY (avoids dark pattern).
 */

import { useMemo, useState } from "react";

export type EnConsentValue = {
  tosPrivacy: boolean;
  marketing: boolean;
};

export type KoConsentValue = {
  collectUse: boolean;
  thirdParty: boolean;
  crossBorder: boolean;
  marketing: boolean;
};

export function ConsentGroupEn({
  value,
  onChange,
  tosPrivacyLabel,
  tosLink,
  privacyLink,
  marketingLabel,
}: {
  value: EnConsentValue;
  onChange: (next: EnConsentValue) => void;
  tosPrivacyLabel: string;
  tosLink: { label: string; href: string };
  privacyLink: { label: string; href: string };
  marketingLabel: string;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-md border border-border bg-bg-muted/40 p-4">
      <label className="flex items-start gap-2 text-sm text-text">
        <input
          type="checkbox"
          checked={value.tosPrivacy}
          onChange={(e) => onChange({ ...value, tosPrivacy: e.target.checked })}
          required
          aria-required="true"
          className="mt-1 h-4 w-4 rounded border-border-strong text-primary-600 focus:ring-2 focus:ring-primary-600/40"
        />
        <span>
          {tosPrivacyLabel}{" "}
          <a
            href={tosLink.href}
            target="_blank"
            rel="noopener"
            className="font-medium text-primary-700 underline"
          >
            {tosLink.label}
          </a>{" "}
          ·{" "}
          <a
            href={privacyLink.href}
            target="_blank"
            rel="noopener"
            className="font-medium text-primary-700 underline"
          >
            {privacyLink.label}
          </a>
        </span>
      </label>
      <label className="flex items-start gap-2 text-sm text-text">
        <input
          type="checkbox"
          checked={value.marketing}
          onChange={(e) => onChange({ ...value, marketing: e.target.checked })}
          className="mt-1 h-4 w-4 rounded border-border-strong text-primary-600 focus:ring-2 focus:ring-primary-600/40"
        />
        <span>{marketingLabel}</span>
      </label>
    </div>
  );
}

export type PipaItem = {
  key: keyof KoConsentValue;
  required: boolean;
  label: string; // [필수] 개인정보 수집·이용 동의 (PIPA §15)
  summary: string; // 항목 / 목적 / 보유
  detail: string; // expand body
};

export function ConsentGroupKo({
  value,
  onChange,
  items,
  masterLabel,
  detailToggleLabel,
  helperRequired,
}: {
  value: KoConsentValue;
  onChange: (next: KoConsentValue) => void;
  items: PipaItem[];
  masterLabel: string;
  detailToggleLabel: string;
  helperRequired: string;
}) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  // Master state: ticked when ALL REQUIRED items are ticked (Kyle Q4 default).
  const requiredItems = items.filter((i) => i.required);
  const allRequired = requiredItems.every((i) => value[i.key]);
  const someRequired = requiredItems.some((i) => value[i.key]);
  const masterChecked = allRequired;
  const masterIndeterminate = someRequired && !allRequired;

  const ref = useMemo(
    () => (el: HTMLInputElement | null) => {
      if (el) el.indeterminate = masterIndeterminate;
    },
    [masterIndeterminate],
  );

  function toggleMaster(checked: boolean) {
    const next: KoConsentValue = { ...value };
    for (const it of requiredItems) next[it.key] = checked;
    onChange(next);
  }

  return (
    <div className="flex flex-col gap-3 rounded-md border border-border bg-bg-muted/40 p-4">
      <label className="flex items-start gap-2 text-sm font-medium text-text">
        <input
          ref={ref}
          type="checkbox"
          checked={masterChecked}
          onChange={(e) => toggleMaster(e.target.checked)}
          aria-checked={masterIndeterminate ? "mixed" : masterChecked}
          className="mt-1 h-4 w-4 rounded border-border-strong text-primary-600 focus:ring-2 focus:ring-primary-600/40"
        />
        <span>{masterLabel}</span>
      </label>
      <hr className="border-border" />
      {items.map((item) => {
        const isOpen = expanded[String(item.key)] ?? false;
        return (
          <div key={String(item.key)} className="flex flex-col gap-1">
            <div className="flex items-start justify-between gap-3">
              <label className="flex items-start gap-2 text-sm text-text">
                <input
                  type="checkbox"
                  checked={Boolean(value[item.key])}
                  onChange={(e) =>
                    onChange({ ...value, [item.key]: e.target.checked })
                  }
                  required={item.required}
                  aria-required={item.required || undefined}
                  className="mt-1 h-4 w-4 rounded border-border-strong text-primary-600 focus:ring-2 focus:ring-primary-600/40"
                />
                <span>
                  <span className="font-medium">{item.label}</span>
                  <span className="block text-xs text-text-muted">{item.summary}</span>
                </span>
              </label>
              <button
                type="button"
                aria-expanded={isOpen}
                onClick={() =>
                  setExpanded((s) => ({ ...s, [String(item.key)]: !isOpen }))
                }
                className="shrink-0 rounded-md border border-border px-2 py-0.5 text-xs text-text-muted hover:bg-bg-muted"
              >
                {detailToggleLabel} {isOpen ? "▲" : "▼"}
              </button>
            </div>
            {isOpen ? (
              <p className="ml-6 rounded-md bg-bg p-2 text-xs text-text-muted">
                {item.detail}
              </p>
            ) : null}
          </div>
        );
      })}
      <p className="text-xs text-text-muted">{helperRequired}</p>
    </div>
  );
}
