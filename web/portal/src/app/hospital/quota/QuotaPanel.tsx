"use client";

import { useEffect, useState } from "react";
import { getDict } from "@/lib/i18n";
import {
  formatBytes,
  formatKstDateTime,
  formatKstDate,
} from "@/components/hospital/format";

/**
 * QuotaPanel — §18.3 page body.
 *
 * Same upstream as the dashboard tile (BFF /api/hospital/me/quota), but
 * a vertical breakdown with explicit sections for daily / monthly /
 * concurrent / ruleset+salt+pixel.
 */

type Quota = {
  daily: { bytes_used: number; bytes_limit: number; resets_at: string };
  monthly: { bytes_used: number; bytes_limit: number; resets_at: string };
  max_concurrent_uploads: number;
  ruleset_version: string;
  salt_version: string;
  salt_rotate_at: string;
  pixel_engine_version: string;
};

function pct(used: number, limit: number): number {
  if (limit <= 0) return 0;
  return Math.min(100, Math.max(0, (used / limit) * 100));
}

function PercentBar({ used, limit }: { used: number; limit: number }) {
  const p = pct(used, limit);
  const tone =
    p >= 90 ? "bg-red-600" : p >= 70 ? "bg-amber-600" : "bg-teal-600";
  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={limit}
      aria-valuenow={used}
      className="h-3 w-full overflow-hidden rounded-pill bg-bg-muted"
    >
      <div className={`h-full rounded-pill ${tone}`} style={{ width: `${p}%` }} />
    </div>
  );
}

export function QuotaPanel({ testId = "quota-panel" }: { testId?: string } = {}) {
  const dict = getDict("ko");
  const [data, setData] = useState<Quota | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const res = await fetch("/api/hospital/me/quota");
        if (!active) return;
        if (!res.ok) {
          setError(true);
          return;
        }
        const body = await res.json();
        setData(body);
        setError(false);
      } catch {
        if (active) setError(true);
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, []);

  if (error) {
    return (
      <div data-testid={`${testId}-error`} className="card mt-4 p-4 text-sm text-text-muted">
        {dict.hospital.quota.fetchFailed}
      </div>
    );
  }
  if (!data) {
    return (
      <div data-testid={`${testId}-loading`} className="card mt-4 p-4">
        <span className="skeleton inline-block h-5 w-40" />
      </div>
    );
  }

  const dailyPctText = pct(data.daily.bytes_used, data.daily.bytes_limit).toFixed(1);
  const monthlyPctText = pct(data.monthly.bytes_used, data.monthly.bytes_limit).toFixed(1);

  return (
    <div data-testid={testId} className="mt-4 flex flex-col gap-4">
      <section className="card flex flex-col gap-2 p-4" data-testid="quota-daily">
        <h2 className="text-sm font-semibold text-text">
          {dict.hospital.quota.daily}
        </h2>
        <PercentBar used={data.daily.bytes_used} limit={data.daily.bytes_limit} />
        <div className="text-sm text-text">
          <span className="tabular-nums">{formatBytes(data.daily.bytes_used)}</span>{" "}
          <span className="text-text-muted">/</span>{" "}
          <span className="tabular-nums">{formatBytes(data.daily.bytes_limit)}</span>{" "}
          <span className="text-text-muted">({dailyPctText}%)</span>
        </div>
        <div className="text-xs text-text-muted">
          {dict.hospital.quota.reset}: {formatKstDateTime(data.daily.resets_at)}
        </div>
      </section>

      <section className="card flex flex-col gap-2 p-4" data-testid="quota-monthly">
        <h2 className="text-sm font-semibold text-text">
          {dict.hospital.quota.monthly}
        </h2>
        <PercentBar used={data.monthly.bytes_used} limit={data.monthly.bytes_limit} />
        <div className="text-sm text-text">
          <span className="tabular-nums">{formatBytes(data.monthly.bytes_used)}</span>{" "}
          <span className="text-text-muted">/</span>{" "}
          <span className="tabular-nums">{formatBytes(data.monthly.bytes_limit)}</span>{" "}
          <span className="text-text-muted">({monthlyPctText}%)</span>
        </div>
        <div className="text-xs text-text-muted">
          {dict.hospital.quota.reset}: {formatKstDateTime(data.monthly.resets_at)}
        </div>
      </section>

      <section className="card flex flex-col gap-1 p-4" data-testid="quota-concurrent">
        <h2 className="text-sm font-semibold text-text">
          {dict.hospital.quota.concurrent}
        </h2>
        <div className="text-2xl font-semibold tabular-nums text-text-strong">
          {data.max_concurrent_uploads}
        </div>
        <div className="text-xs text-text-muted">
          {dict.hospital.quota.maxConcurrentLabel} · {dict.hospital.quota.maxConcurrentNote}
        </div>
      </section>

      <section className="card flex flex-col gap-2 p-4" data-testid="quota-ruleset">
        <h2 className="text-sm font-semibold text-text">
          Ruleset / Salt / Pixel Engine
        </h2>
        <dl className="grid grid-cols-[10rem_1fr] gap-y-1 text-sm">
          <dt className="text-text-muted">de-id ruleset</dt>
          <dd className="font-mono text-text">{data.ruleset_version}</dd>
          <dt className="text-text-muted">salt 버전</dt>
          <dd className="font-mono text-text">
            {data.salt_version}
            <span className="ml-2 text-xs text-text-muted">
              (다음 rotate: {formatKstDate(data.salt_rotate_at)})
            </span>
          </dd>
          <dt className="text-text-muted">pixel engine</dt>
          <dd className="font-mono text-text">{data.pixel_engine_version}</dd>
        </dl>
      </section>

      <p className="text-xs text-text-muted">
        ⓘ {dict.hospital.quota.enforceDisclaimer}
      </p>
    </div>
  );
}
