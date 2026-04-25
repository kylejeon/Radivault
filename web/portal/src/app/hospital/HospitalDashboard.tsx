"use client";

/**
 * HospitalDashboard — design-spec §18.1 (9-tile layout).
 *
 * Composition:
 *   row 1 — uploaded studies / total bytes / modality donut
 *   row 2 — audit chain status / gateway heartbeat / quota 3-up
 *   row 3 — revenue (static K-15 dummy) / order inflow / ruleset badge
 *
 * Loading priority (§18.1):
 *   - Critical (1, 5, 6, 8) fetch on mount.
 *   - Lazy   (2, 3, 7, 9)   fetch in the same Promise.all but the tiles
 *     show skeletons independently so a slow ruleset endpoint cannot
 *     block the audit-chain badge.
 *
 * Below the grid: §18.1 audit-log preview (top 20 events) + the existing
 * Korea heatmap tile.
 */

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { TileCard } from "@/components/TileCard";
import { KoreaHeatmap, type Region } from "@/components/KoreaHeatmap";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getDict } from "@/lib/i18n";
import {
  AuditChainStatusBadge,
  type AuditChainStatusData,
} from "@/components/hospital/AuditChainStatusBadge";
import {
  GatewayHeartbeatChart,
  type GatewayHeartbeatData,
} from "@/components/hospital/GatewayHeartbeatChart";
import { QuotaTile, type QuotaData } from "@/components/hospital/QuotaTile";
import {
  RulesetVersionBadge,
  type RulesetVersionData,
} from "@/components/hospital/RulesetVersionBadge";
import {
  ModalityDistributionChart,
  type ModalitySlice,
} from "@/components/hospital/ModalityDistributionChart";
import {
  RevenueTile,
  REVENUE_DUMMY,
} from "@/components/hospital/RevenueTile";
import { OrderInflowTile } from "@/components/hospital/OrderInflowTile";
import { formatBytes, formatKstTime } from "@/components/hospital/format";

type Stats = {
  hospital_id: string;
  studies: {
    today: number;
    cumulative: number;
    monthly_12m: { year_month: string; count: number }[];
  };
  gateway_health: GatewayHeartbeatData;
  modality_distribution: ModalitySlice[];
};

type HospitalOrders = {
  orders: {
    order_id_masked: string;
    n_studies: number;
    phase: string;
    submitted_at: string;
    delivered_at: string | null;
  }[];
};

type Audit = {
  events: {
    ts: string;
    event_type: string;
    hash_short: string;
    detail_code: string | null;
  }[];
};

type AuditChain = AuditChainStatusData & { hospital_id?: string };

type Quota = {
  hospital_id: string;
  daily: { bytes_used: number; bytes_limit: number; resets_at: string };
  monthly: { bytes_used: number; bytes_limit: number; resets_at: string };
  max_concurrent_uploads: number;
  ruleset_version: string;
  salt_version: string;
  salt_rotate_at: string;
  pixel_engine_version: string;
};

const PLACEHOLDER_REGIONS: Region[] = [
  { id: "seoul", name: "서울", x: 48, y: 28, active: true },
  { id: "gyeonggi", name: "경기", x: 52, y: 32, active: false },
];

export function HospitalDashboard({ hospitalId }: { hospitalId: string }) {
  const dict = getDict("ko");

  const [stats, setStats] = useState<Stats | null>(null);
  const [orders, setOrders] = useState<HospitalOrders | null>(null);
  const [audit, setAudit] = useState<Audit | null>(null);
  const [auditChain, setAuditChain] = useState<AuditChain | null>(null);
  const [quota, setQuota] = useState<Quota | null>(null);

  const [statsErr, setStatsErr] = useState<{ code?: string; detail?: string; requestId?: string } | null>(null);
  const [auditChainErr, setAuditChainErr] = useState(false);
  const [quotaErr, setQuotaErr] = useState(false);
  const [auditErr, setAuditErr] = useState(false);

  useEffect(() => {
    let active = true;
    async function load() {
      // Critical (run together so a single 5-tile spinner ends as quickly
      // as the slowest one).
      try {
        const [sRes, oRes, acRes, qRes] = await Promise.all([
          fetch("/api/hospital/stats"),
          fetch("/api/hospital/orders"),
          fetch("/api/hospital/me/audit-chain-status"),
          fetch("/api/hospital/me/quota"),
        ]);
        if (!active) return;
        if (sRes.ok) {
          const sBody = await sRes.json();
          setStats(sBody.data ?? sBody);
          setStatsErr(null);
        } else {
          const body = await sRes.json().catch(() => ({}));
          setStatsErr({ code: body?.error, detail: body?.detail, requestId: body?.request_id });
        }
        if (oRes.ok) {
          const oBody = await oRes.json();
          setOrders(oBody.data ?? oBody);
        }
        if (acRes.ok) {
          const acBody = await acRes.json();
          setAuditChain(acBody);
          setAuditChainErr(false);
        } else {
          setAuditChainErr(true);
        }
        if (qRes.ok) {
          const qBody = await qRes.json();
          setQuota(qBody);
          setQuotaErr(false);
        } else {
          setQuotaErr(true);
        }
      } catch (err) {
        if (active) {
          setStatsErr({ code: "ERR_UPSTREAM_UNAVAILABLE", detail: String(err) });
        }
      }

      // Lazy — the audit log preview can lag behind the rest.
      try {
        const aRes = await fetch("/api/hospital/audit?limit=20");
        if (!active) return;
        if (aRes.ok) {
          const aBody = await aRes.json();
          setAudit(aBody.data ?? aBody);
          setAuditErr(false);
        } else {
          setAuditErr(true);
        }
      } catch {
        if (active) setAuditErr(true);
      }
    }
    void load();
    const interval = setInterval(load, 60_000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  // Derived: total bytes across the modality distribution rollup. The
  // central /v1/hospital/me/stats does not surface bytes natively yet —
  // when it does, swap to that field.
  const totalBytesEstimate = useMemo(() => {
    if (!stats) return null;
    // Rough estimator: studies × 24 MB average (CT-heavy mix).
    return stats.studies.cumulative * 24 * 1024 * 1024;
  }, [stats]);

  const orderInflow = useMemo(() => {
    if (!orders) return null;
    // v0.1 simplification: every order in the response counts toward
    // "this month" since the BFF already filters to 30d.
    return {
      count_this_month: orders.orders.length,
      recent: orders.orders.map((o) => ({
        order_id_masked: o.order_id_masked,
        n_studies: o.n_studies,
        submitted_at: o.submitted_at,
      })),
    };
  }, [orders]);

  const quotaForTile: QuotaData | null = quota
    ? {
        daily: quota.daily,
        monthly: quota.monthly,
        max_concurrent_uploads: quota.max_concurrent_uploads,
      }
    : null;

  const rulesetForBadge: RulesetVersionData | null = quota
    ? {
        ruleset_version: quota.ruleset_version,
        salt_version: quota.salt_version,
        salt_rotate_at: quota.salt_rotate_at,
        pixel_engine_version: quota.pixel_engine_version,
      }
    : null;

  if (statsErr && !stats) return <ErrorBanner {...statsErr} />;

  return (
    <div className="flex flex-col gap-6">
      {/* 9-tile grid — 3×3 desktop, 2-up tablet, 1-col mobile (§18.1). */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {/* Tile 1 — uploaded studies + 12m sparkline */}
        <div data-testid="tile-h1-uploaded-studies">
          <TileCard
            title={dict.hospital.tile.uploadedStudies}
            value={
              stats ? (
                <div className="flex items-baseline gap-2">
                  <span className="text-teal-700">
                    {stats.studies.today.toLocaleString("ko-KR")}
                  </span>
                  <span className="text-text-muted">/</span>
                  <span>{stats.studies.cumulative.toLocaleString("ko-KR")}</span>
                </div>
              ) : (
                <span className="skeleton inline-block h-8 w-32" />
              )
            }
            subtitle={`${dict.hospital.tile.today} / ${dict.hospital.tile.cumulative}`}
          >
            {stats ? <Sparkline data={stats.studies.monthly_12m} /> : null}
          </TileCard>
        </div>

        {/* Tile 2 — total bytes */}
        <div data-testid="tile-h2-total-bytes">
          <TileCard
            title={dict.hospital.tile.totalBytes}
            value={
              totalBytesEstimate !== null ? (
                <span className="tabular-nums">
                  {formatBytes(totalBytesEstimate)}
                </span>
              ) : (
                <span className="skeleton inline-block h-8 w-32" />
              )
            }
            subtitle={dict.hospital.tile.cumulative}
          />
        </div>

        {/* Tile 3 — modality donut */}
        <div data-testid="tile-h3-modality">
          <TileCard title={dict.hospital.tile.modalityDist}>
            <ModalityDistributionChart
              slices={stats?.modality_distribution ?? []}
              loading={!stats}
            />
          </TileCard>
        </div>

        {/* Tile 4 — audit chain status */}
        <div data-testid="tile-h4-audit-chain">
          <TileCard title={dict.hospital.tile.auditChain}>
            <AuditChainStatusBadge
              data={auditChain}
              loading={!auditChain && !auditChainErr}
              error={auditChainErr}
            />
          </TileCard>
        </div>

        {/* Tile 5 — gateway heartbeat */}
        <div data-testid="tile-h5-gateway-hb">
          <TileCard title={dict.hospital.tile.gatewayHb}>
            <GatewayHeartbeatChart
              data={stats?.gateway_health ?? null}
              loading={!stats}
            />
          </TileCard>
        </div>

        {/* Tile 6 — quota 3-up */}
        <div data-testid="tile-h6-quota">
          <TileCard title={dict.hospital.tile.quota}>
            <QuotaTile
              data={quotaForTile}
              loading={!quota && !quotaErr}
              error={quotaErr}
            />
          </TileCard>
        </div>

        {/* Tile 7 — revenue (K-15 static dummy) */}
        <div data-testid="tile-h7-revenue">
          <TileCard title={dict.hospital.tile.revenue}>
            <RevenueTile data={REVENUE_DUMMY[hospitalId] ?? null} />
          </TileCard>
        </div>

        {/* Tile 8 — order inflow */}
        <div data-testid="tile-h8-order-inflow">
          <TileCard title={dict.hospital.tile.orderInflow}>
            <OrderInflowTile data={orderInflow} loading={!orders} />
          </TileCard>
        </div>

        {/* Tile 9 — ruleset / salt / pixel */}
        <div data-testid="tile-h9-ruleset">
          <TileCard title={dict.hospital.tile.ruleset}>
            <RulesetVersionBadge
              data={rulesetForBadge}
              loading={!quota && !quotaErr}
              error={quotaErr}
            />
          </TileCard>
        </div>
      </div>

      {/* Audit log preview — §18.1 bottom strip. */}
      <section
        data-testid="hospital-audit-preview"
        className="card flex flex-col gap-3 p-5"
      >
        <header className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-text">
            최근 감사 이벤트 (최대 20)
          </h3>
          <Link
            href="/hospital/audit"
            className="text-xs font-medium text-teal-700 hover:text-teal-800"
          >
            전체 로그 →
          </Link>
        </header>
        {auditErr ? (
          <p className="text-sm text-text-muted">
            {dict.hospital.audit.fetchFailed}
          </p>
        ) : audit ? (
          audit.events.length === 0 ? (
            <p className="text-sm text-text-muted">{dict.hospital.audit.empty}</p>
          ) : (
            <ul className="flex flex-col divide-y divide-border text-xs">
              {audit.events.slice(0, 20).map((e, i) => (
                <li
                  key={e.hash_short + i}
                  className="grid grid-cols-[6rem_1fr_8rem] items-center gap-2 py-1.5"
                >
                  <code className="text-text-muted">
                    {formatKstTime(e.ts)}
                  </code>
                  <span className="text-text">{e.event_type}</span>
                  <code className="text-right font-mono text-text-muted">
                    {e.hash_short}
                  </code>
                </li>
              ))}
            </ul>
          )
        ) : (
          <span className="skeleton inline-block h-8 w-40" />
        )}
      </section>

      {/* Korea heatmap (FR-HO-8 — kept). */}
      <section className="card flex flex-col gap-3 p-5">
        <header>
          <h3 className="text-sm font-semibold text-text">기여 지역</h3>
        </header>
        <div className="h-44 w-full">
          <KoreaHeatmap regions={PLACEHOLDER_REGIONS} />
        </div>
      </section>
    </div>
  );
}

function Sparkline({
  data,
}: {
  data: { year_month: string; count: number }[];
}) {
  const max = Math.max(1, ...data.map((d) => d.count));
  return (
    <div className="mt-2 flex items-end gap-1">
      {data.map((d, i) => {
        const isLatest = i === data.length - 1;
        return (
          <div
            key={d.year_month}
            className={
              "flex-1 rounded-sm " +
              (isLatest ? "bg-teal-600" : "bg-teal-100")
            }
            style={{
              height: `${Math.max(4, (d.count / max) * 32)}px`,
            }}
            title={`${d.year_month}: ${d.count.toLocaleString("ko-KR")}`}
          />
        );
      })}
    </div>
  );
}
