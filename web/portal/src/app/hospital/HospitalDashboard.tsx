"use client";

import { useEffect, useState } from "react";
import { TileCard } from "@/components/TileCard";
import { KoreaHeatmap, type Region } from "@/components/KoreaHeatmap";
import { ErrorBanner } from "@/components/ErrorBanner";

type Stats = {
  hospital_id: string;
  studies: {
    today: number;
    cumulative: number;
    monthly_12m: { year_month: string; count: number }[];
  };
  gateway_health: {
    status: "online" | "warning" | "offline" | "unknown";
    last_sync_at: string | null;
    last_sync_delta_seconds: number | null;
  };
  modality_distribution: { modality: string; count: number }[];
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

// Demo-only revenue simulation (dev-spec §11.2 Q-Demo-2 pending Kyle decision).
// Values are clearly marked as simulation in the tile footer.
const UNIT_PRICE_USD = 5;
const HOSPITAL_SHARE = 0.35;
const KRW_PER_USD = 1350;

function simulateRevenueKrw(cumulative: number): number {
  return Math.round(cumulative * UNIT_PRICE_USD * HOSPITAL_SHARE * KRW_PER_USD);
}

function statusPillClass(status: Stats["gateway_health"]["status"]): string {
  switch (status) {
    case "online":
      return "text-green-700";
    case "warning":
      return "text-yellow-700";
    case "offline":
      return "text-red-700";
    default:
      return "text-slate-500";
  }
}

function statusLabelKo(status: Stats["gateway_health"]["status"]): string {
  return { online: "정상", warning: "주의", offline: "연결 끊김", unknown: "확인 중" }[status];
}

const PLACEHOLDER_REGIONS: Region[] = [
  { id: "seoul", name: "서울", x: 48, y: 28, active: true },
  { id: "daejeon", name: "대전", x: 52, y: 56, active: false },
];

export function HospitalDashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [orders, setOrders] = useState<HospitalOrders | null>(null);
  const [audit, setAudit] = useState<Audit | null>(null);
  const [error, setError] = useState<{ code?: string; detail?: string; requestId?: string } | null>(
    null,
  );

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const [sRes, oRes, aRes] = await Promise.all([
          fetch("/api/hospital/stats"),
          fetch("/api/hospital/orders"),
          fetch("/api/hospital/audit"),
        ]);
        if (!active) return;
        if (!sRes.ok) {
          const body = await sRes.json().catch(() => ({}));
          setError({ code: body?.error, detail: body?.detail, requestId: body?.request_id });
          return;
        }
        const sBody = await sRes.json();
        setStats(sBody.data ?? sBody);
        if (oRes.ok) {
          const oBody = await oRes.json();
          setOrders(oBody.data ?? oBody);
        }
        if (aRes.ok) {
          const aBody = await aRes.json();
          setAudit(aBody.data ?? aBody);
        }
        setError(null);
      } catch (err) {
        setError({ code: "ERR_UPSTREAM_UNAVAILABLE", detail: String(err) });
      }
    }
    void load();
    const interval = setInterval(load, 60_000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  if (error && !stats) return <ErrorBanner {...error} />;

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
      <TileCard
        title="오늘 / 누적 제공 스터디"
        value={
          stats ? (
            <div>
              <span className="text-primary">{stats.studies.today.toLocaleString()}</span>
              <span className="mx-2 text-ink-subtle">/</span>
              <span>{stats.studies.cumulative.toLocaleString()}</span>
            </div>
          ) : (
            <span className="skeleton inline-block h-8 w-32" />
          )
        }
        subtitle="오늘 / 누적"
      />

      <TileCard
        title="예상 수익 (시뮬레이션)"
        value={
          stats ? (
            <span>₩ {simulateRevenueKrw(stats.studies.cumulative).toLocaleString("ko-KR")}</span>
          ) : (
            <span className="skeleton inline-block h-8 w-36" />
          )
        }
        subtitle="누계"
        footer="시뮬레이션 — v0.2 정산 대기"
      >
        {stats ? (
          <MonthlyBarChart data={stats.studies.monthly_12m} />
        ) : null}
      </TileCard>

      <TileCard title="기여 지역">
        <div className="h-44 w-full">
          <KoreaHeatmap regions={PLACEHOLDER_REGIONS} />
        </div>
      </TileCard>

      <TileCard title="Gateway 상태">
        {stats ? (
          <div className="flex flex-col gap-2">
            <div className={"flex items-center gap-2 text-lg font-semibold " + statusPillClass(stats.gateway_health.status)}>
              <span className="inline-block size-2.5 rounded-full bg-current" />
              {statusLabelKo(stats.gateway_health.status)}
            </div>
            {stats.gateway_health.last_sync_at ? (
              <div className="text-xs text-ink-subtle">
                마지막 동기화:{" "}
                {new Date(stats.gateway_health.last_sync_at).toLocaleTimeString("ko-KR")}
              </div>
            ) : (
              <div className="text-xs text-ink-subtle">동기화 기록 없음</div>
            )}
          </div>
        ) : (
          <span className="skeleton inline-block h-8 w-24" />
        )}
      </TileCard>

      <TileCard title="최근 주문 스트림">
        {orders ? (
          orders.orders.length === 0 ? (
            <p className="text-sm text-ink-subtle">아직 주문이 없습니다.</p>
          ) : (
            <ul className="flex flex-col gap-1.5 text-sm">
              {orders.orders.slice(0, 5).map((o) => (
                <li key={o.order_id_masked + o.submitted_at} className="flex items-center justify-between">
                  <code className="font-mono text-xs text-ink-muted">{o.order_id_masked}</code>
                  <span>{o.n_studies.toLocaleString()} 스터디</span>
                  <span className="text-xs text-ink-subtle">{o.phase}</span>
                </li>
              ))}
            </ul>
          )
        ) : (
          <span className="skeleton inline-block h-8 w-32" />
        )}
      </TileCard>

      <TileCard title="최근 감사 이벤트">
        {audit ? (
          <ul className="flex flex-col gap-1 text-xs">
            {audit.events.slice(0, 10).map((e, i) => (
              <li key={e.hash_short + i} className="grid grid-cols-[5rem_1fr_5rem] items-center gap-2">
                <code className="text-ink-subtle">
                  {new Date(e.ts).toLocaleTimeString("ko-KR")}
                </code>
                <span>{e.event_type}</span>
                <code className="text-right font-mono text-ink-subtle">{e.hash_short}</code>
              </li>
            ))}
            {audit.events.length === 0 ? (
              <li className="text-ink-subtle">이벤트 없음</li>
            ) : null}
          </ul>
        ) : (
          <span className="skeleton inline-block h-8 w-32" />
        )}
      </TileCard>
    </div>
  );
}

function MonthlyBarChart({
  data,
}: {
  data: { year_month: string; count: number }[];
}) {
  const max = Math.max(1, ...data.map((d) => d.count));
  return (
    <div className="mt-2 flex items-end gap-1">
      {data.map((d) => (
        <div
          key={d.year_month}
          className="flex-1 rounded-sm bg-primary-soft"
          style={{
            height: `${Math.max(4, (d.count / max) * 32)}px`,
          }}
          title={`${d.year_month}: ${d.count.toLocaleString()}`}
        />
      ))}
    </div>
  );
}
