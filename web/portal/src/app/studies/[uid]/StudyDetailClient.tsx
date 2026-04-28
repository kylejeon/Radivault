"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Toaster } from "react-hot-toast";
import { ErrorBanner } from "@/components/ErrorBanner";
import {
  StudyDetailPanel,
  type StudyDetail,
} from "@/components/buyer/StudyDetailPanel";
import { SaMDFooter } from "@/components/preview/SaMDFooter";
import { getDict, type Locale } from "@/lib/i18n";

const COHORT_STORAGE_KEY = "radivault.cohort.v1";

type CohortEntry = StudyDetail & { total_bytes: number };

function loadCohort(): Record<string, CohortEntry> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.sessionStorage.getItem(COHORT_STORAGE_KEY);
    if (!raw) return {};
    return JSON.parse(raw) as Record<string, CohortEntry>;
  } catch {
    return {};
  }
}

function saveCohort(cohort: Record<string, CohortEntry>) {
  try {
    window.sessionStorage.setItem(COHORT_STORAGE_KEY, JSON.stringify(cohort));
  } catch {
    /* ignore */
  }
}

export function StudyDetailClient({
  uid,
  locale = "en",
}: {
  uid: string;
  locale?: Locale;
}) {
  const dict = getDict(locale);
  const [study, setStudy] = useState<StudyDetail | null>(null);
  const [error, setError] = useState<{
    code?: string;
    detail?: string;
    requestId?: string;
    status?: number;
  } | null>(null);
  const [inCohort, setInCohort] = useState(false);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const res = await fetch(
          `/api/search/studies/${encodeURIComponent(uid)}`,
        );
        if (!active) return;
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          setError({
            code: body?.error,
            detail: body?.detail,
            requestId: body?.request_id,
            status: res.status,
          });
          return;
        }
        const data = (await res.json()) as StudyDetail;
        setStudy(data);
      } catch (err) {
        setError({
          code: "ERR_UPSTREAM_UNAVAILABLE",
          detail: String(err),
        });
      }
    })();
    return () => {
      active = false;
    };
  }, [uid]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const cohort = loadCohort();
    setInCohort(Boolean(cohort[uid]));
  }, [uid]);

  function addToCohort() {
    if (!study) return;
    const cohort = loadCohort();
    cohort[study.pseudo_study_uid] = study;
    saveCohort(cohort);
    setInCohort(true);
  }

  if (error) {
    if (error.status === 404) {
      return (
        <main className="mx-auto max-w-content px-6 py-6">
          <div className="rounded-md border border-border bg-bg-muted px-6 py-12 text-center">
            <h1 className="text-lg font-semibold text-text">
              {dict.study.notFoundTitle}
            </h1>
            <p className="mx-auto mt-2 max-w-prose text-sm text-text-muted">
              {dict.study.notFoundBody}
            </p>
            <Link
              href="/search"
              className="mt-4 inline-flex rounded-md bg-primary-600 px-3 py-1.5 text-sm font-medium text-white"
            >
              ← {dict.study.backToResults}
            </Link>
          </div>
        </main>
      );
    }
    return (
      <main className="mx-auto max-w-content px-6 py-6">
        <ErrorBanner
          code={error.code}
          requestId={error.requestId}
          detail={error.detail}
        />
      </main>
    );
  }

  if (!study) {
    return (
      <main className="mx-auto max-w-content px-6 py-6">
        <div className="flex flex-col gap-3">
          <div className="h-10 animate-pulse rounded-md bg-bg-muted" />
          <div className="h-64 animate-pulse rounded-md bg-bg-muted" />
        </div>
      </main>
    );
  }

  // Full-bleed: <StudyDetailPanel> renders the v3 sub-bar + dark viewer pane
  // + right rail + collapsible compliance footer end-to-end. The page-level
  // <SaMDFooter> stays as a sticky bottom band underneath the collapsible
  // compliance section so the medical-device disclaimer is always visible.
  return (
    <>
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: { fontSize: "13px" },
        }}
      />
      <StudyDetailPanel
        study={study}
        onAddToCohort={addToCohort}
        alreadyInCohort={inCohort}
        locale={locale}
      />
      <SaMDFooter locale={locale} />
    </>
  );
}
