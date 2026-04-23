"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { FacetGroup } from "@/components/FacetGroup";
import { StudyCard } from "@/components/StudyCard";
import { CohortSummary } from "@/components/CohortSummary";
import { EmptyState } from "@/components/EmptyState";
import { ErrorBanner } from "@/components/ErrorBanner";
import { ReviewOrderModal } from "./ReviewOrderModal";

type FacetResp = {
  modality?: { value: string; count: number }[];
  body_part?: { value: string; count: number }[];
  sex?: { value: string; count: number }[];
  manufacturer?: { value: string; count: number }[];
};

type SearchStudy = {
  pseudo_study_uid: string;
  modality: string | null;
  body_part: string | null;
  n_instances: number;
  total_bytes: number;
  study_year: number | null;
};

type SearchResp = {
  items: SearchStudy[];
  total: number;
  next_cursor?: string | null;
};

type Filters = {
  modality: Set<string>;
  body_part: Set<string>;
  sex: Set<string>;
  manufacturer: Set<string>;
};

function emptyFilters(): Filters {
  return {
    modality: new Set(),
    body_part: new Set(),
    sex: new Set(),
    manufacturer: new Set(),
  };
}

export function SearchApp() {
  const router = useRouter();
  const [facets, setFacets] = useState<FacetResp | null>(null);
  const [results, setResults] = useState<SearchResp | null>(null);
  const [filters, setFilters] = useState<Filters>(emptyFilters());
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [error, setError] = useState<{ code?: string; detail?: string; requestId?: string } | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [reviewOpen, setReviewOpen] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        const [fRes, sRes] = await Promise.all([
          fetch("/api/search/facets"),
          fetch("/api/search/studies", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ page_size: 25 }),
          }),
        ]);
        if (fRes.status === 401 || sRes.status === 401) {
          router.push("/signin");
          return;
        }
        if (!fRes.ok) {
          const body = await fRes.json().catch(() => ({}));
          setError({ code: body?.error, detail: body?.detail, requestId: body?.request_id });
        } else {
          setFacets(await fRes.json());
        }
        if (!sRes.ok) {
          const body = await sRes.json().catch(() => ({}));
          setError({ code: body?.error, detail: body?.detail, requestId: body?.request_id });
        } else {
          setResults(await sRes.json());
        }
      } finally {
        setLoading(false);
      }
    })();
  }, [router]);

  useEffect(() => {
    // Re-query on filter change.
    if (loading) return;
    const body = {
      modalities: Array.from(filters.modality),
      body_parts: Array.from(filters.body_part),
      sex: Array.from(filters.sex),
      manufacturers: Array.from(filters.manufacturer),
      page_size: 25,
    };
    void (async () => {
      try {
        const res = await fetch("/api/search/studies", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!res.ok) {
          const bodyJson = await res.json().catch(() => ({}));
          setError({
            code: bodyJson?.error,
            detail: bodyJson?.detail,
            requestId: bodyJson?.request_id,
          });
          return;
        }
        setResults(await res.json());
        setError(null);
      } catch (err) {
        setError({ code: "ERR_UPSTREAM_UNAVAILABLE", detail: String(err) });
      }
    })();
  }, [filters, loading]);

  const totalSizeMb = useMemo(() => {
    if (!results) return 0;
    let bytes = 0;
    for (const it of results.items) {
      if (selected.has(it.pseudo_study_uid)) bytes += it.total_bytes;
    }
    return bytes / (1024 * 1024);
  }, [results, selected]);

  const toggle =
    (facet: keyof Filters) =>
    (value: string) => {
      setFilters((prev) => {
        const next = new Set(prev[facet]);
        if (next.has(value)) next.delete(value);
        else next.add(value);
        return { ...prev, [facet]: next };
      });
    };

  const toggleStudy = (uid: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(uid)) next.delete(uid);
      else next.add(uid);
      return next;
    });
  };

  return (
    <div className="grid grid-cols-[18rem_1fr_18rem] gap-4">
      <div className="flex flex-col gap-4">
        {facets?.modality ? (
          <FacetGroup
            label="Modality"
            facet="modality"
            items={facets.modality}
            selected={filters.modality}
            onToggle={toggle("modality")}
          />
        ) : (
          <SkeletonFacet />
        )}
        {facets?.body_part ? (
          <FacetGroup
            label="Body part"
            facet="body_part"
            items={facets.body_part}
            selected={filters.body_part}
            onToggle={toggle("body_part")}
          />
        ) : (
          <SkeletonFacet />
        )}
        {facets?.sex ? (
          <FacetGroup
            label="Sex"
            facet="sex"
            items={facets.sex}
            selected={filters.sex}
            onToggle={toggle("sex")}
          />
        ) : (
          <SkeletonFacet />
        )}
      </div>

      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between px-1">
          <h2 className="text-sm font-medium text-ink-muted">
            {results
              ? `${results.items.length.toLocaleString()} of ${results.total.toLocaleString()} studies`
              : "Loading…"}
          </h2>
        </div>
        {error ? (
          <ErrorBanner code={error.code} requestId={error.requestId} detail={error.detail} />
        ) : null}
        {!loading && results && results.items.length === 0 ? (
          <EmptyState
            title="No studies match these filters"
            body="Try widening your date range or removing the min-hospitals constraint."
          />
        ) : null}
        {loading ? (
          <div className="flex flex-col gap-2">
            {[0, 1, 2, 3, 4].map((i) => (
              <div key={i} className="card h-16 animate-pulse" />
            ))}
          </div>
        ) : null}
        {results?.items.map((study) => {
          const sizeMb = study.total_bytes / (1024 * 1024);
          return (
            <StudyCard
              key={study.pseudo_study_uid}
              pseudoStudyUid={study.pseudo_study_uid}
              modality={study.modality}
              bodyPart={study.body_part}
              nInstances={study.n_instances}
              sizeMb={sizeMb}
              studyYear={study.study_year}
              selected={selected.has(study.pseudo_study_uid)}
              onToggle={() => toggleStudy(study.pseudo_study_uid)}
            />
          );
        })}
      </div>

      <div>
        <CohortSummary
          count={selected.size}
          totalSizeMb={totalSizeMb}
          onReview={() => setReviewOpen(true)}
        />
      </div>

      {reviewOpen ? (
        <ReviewOrderModal
          uids={Array.from(selected)}
          totalSizeMb={totalSizeMb}
          onClose={() => setReviewOpen(false)}
        />
      ) : null}
    </div>
  );
}

function SkeletonFacet() {
  return <div className="card h-44 animate-pulse" />;
}
