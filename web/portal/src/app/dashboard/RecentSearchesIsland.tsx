"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

/**
 * Recent searches tile — reads the same localStorage key SearchApp.tsx
 * writes to (FR-BP-15). Server renders the tile shell; this island
 * hydrates the body so the SSR pass doesn't trigger a hydration mismatch
 * on per-user data.
 */

const STORAGE_KEY = "radivault.recent-searches.v1";

type RecentSearch = {
  label: string;
  href: string;
  at: number;
};

function loadRecent(): RecentSearch[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    // Defensive: drop entries missing required fields.
    return parsed
      .filter(
        (e): e is RecentSearch =>
          !!e &&
          typeof (e as RecentSearch).label === "string" &&
          typeof (e as RecentSearch).href === "string",
      )
      .slice(0, 5);
  } catch {
    return [];
  }
}

export function DashboardRecentSearches({
  empty,
  cta,
}: {
  empty: string;
  cta: string;
}) {
  const [searches, setSearches] = useState<RecentSearch[] | null>(null);

  useEffect(() => {
    setSearches(loadRecent());
  }, []);

  if (searches === null) {
    return <div aria-hidden className="h-6 animate-pulse rounded bg-bg-muted" />;
  }

  if (searches.length === 0) {
    return (
      <>
        <p className="text-sm text-text-muted">{empty}</p>
        <Link
          href="/search"
          className="mt-3 inline-flex text-sm font-medium text-primary-700 hover:underline"
        >
          {cta} →
        </Link>
      </>
    );
  }

  return (
    <ul className="flex flex-col gap-1.5 text-sm">
      {searches.map((s) => (
        <li key={`${s.href}-${s.at}`} className="truncate">
          <Link
            href={s.href}
            className="text-primary-700 hover:underline"
            data-testid="dashboard-recent-search-item"
          >
            {s.label}
          </Link>
        </li>
      ))}
    </ul>
  );
}
