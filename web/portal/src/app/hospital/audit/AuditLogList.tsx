"use client";

import { useEffect, useState } from "react";
import { getDict } from "@/lib/i18n";
import { formatKstDateTime } from "@/components/hospital/format";

/**
 * AuditLogList — §18.2 page body.
 *
 * Reuses the existing GET /api/hospital/audit endpoint (already wired in
 * the v0.1 dashboard) with `limit=20`. Each row exposes: KST timestamp,
 * event type, hash prefix, chain status (always ✓ in v0.1 — chain
 * tampering surfaces via the AuditChainStatusBadge tile, not here).
 */

type Event = {
  ts: string;
  event_type: string;
  hash_short: string;
  detail_code: string | null;
};

export function AuditLogList({ testId = "audit-log-list" }: { testId?: string } = {}) {
  const dict = getDict("ko");
  const [events, setEvents] = useState<Event[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const res = await fetch("/api/hospital/audit?limit=20");
        if (!active) return;
        if (!res.ok) {
          setError(true);
          return;
        }
        const body = await res.json();
        setEvents((body?.data ?? body)?.events ?? []);
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
      <p data-testid={`${testId}-error`} className="text-sm text-text-muted">
        {dict.hospital.audit.fetchFailed}
      </p>
    );
  }
  if (events === null) {
    return (
      <ul data-testid={`${testId}-loading`} className="flex flex-col gap-2">
        {Array.from({ length: 10 }).map((_, i) => (
          <li key={i} className="skeleton h-5 w-full" />
        ))}
      </ul>
    );
  }
  if (events.length === 0) {
    return (
      <p data-testid={`${testId}-empty`} className="text-sm text-text-muted">
        {dict.hospital.audit.empty}
      </p>
    );
  }
  return (
    <table
      data-testid={testId}
      className="w-full text-left text-sm"
      role="table"
    >
      <thead className="text-xs uppercase tracking-wide text-text-muted">
        <tr className="border-b border-border">
          <th className="w-56 px-2 py-2 font-medium">
            {dict.hospital.audit.column.time}
          </th>
          <th className="w-48 px-2 py-2 font-medium">
            {dict.hospital.audit.column.type}
          </th>
          <th className="px-2 py-2 font-medium">
            {dict.hospital.audit.column.hash}
          </th>
          <th className="w-20 px-2 py-2 text-right font-medium">
            {dict.hospital.audit.column.chain}
          </th>
        </tr>
      </thead>
      <tbody className="divide-y divide-border">
        {events.map((e, i) => (
          <tr key={e.hash_short + i}>
            <td className="px-2 py-2 text-text-muted">
              <code>{formatKstDateTime(e.ts)}</code>
            </td>
            <td className="px-2 py-2 text-text">{e.event_type}</td>
            <td className="px-2 py-2">
              <code className="font-mono text-xs text-text-muted">
                {e.hash_short}
              </code>
            </td>
            <td className="px-2 py-2 text-right text-teal-700" aria-label="chain ok">
              ✓
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
