import type { Page, Route } from "@playwright/test";

/**
 * Route interception helpers (dev-spec §4 BFF API shapes).
 *
 * Every helper registers `page.route` on the exact path (not a regex) so
 * test specs can compose them selectively. The JSON shapes below mirror
 * the real upstream responses surfaced by /src/app/api/*. If the BFF
 * contract changes, update this file first — otherwise the UI will fail
 * to parse mocked payloads and the tests become false positives.
 */

export type ModalityFacet = { value: string; count: number };

export type FacetResponse = {
  modality?: ModalityFacet[];
  body_part?: ModalityFacet[];
  sex?: ModalityFacet[];
  manufacturer?: ModalityFacet[];
};

export type SearchStudy = {
  pseudo_study_uid: string;
  modality: string | null;
  body_part: string | null;
  age_bucket: string | null;
  sex: string | null;
  n_instances: number;
  total_bytes: number;
  study_year: number | null;
  study_date_shifted: string | null;
  hospital_opaque_id: string | null;
};

export type SearchResponse = {
  items: SearchStudy[];
  total: number;
  next_cursor?: string | null;
};

/**
 * Register a canned /api/session handler that succeeds for rv_live_/rv_test_
 * prefixed keys and fails otherwise (mirrors FR-A-4 error taxonomy).
 *
 * The real handler ALSO sets an iron-session cookie, which we can't forge
 * from here (the secret lives server-side). Instead we stub the response
 * with a `Set-Cookie` header that the downstream page can't decrypt — and
 * that's fine because downstream /api/* are also mocked. The cookie simply
 * needs to be non-empty so middleware / cookie gates accept it.
 */
export async function mockBuyerSignIn(page: Page): Promise<void> {
  await page.route("**/api/session", async (route) => {
    const request = route.request();
    if (request.method() !== "POST") {
      await route.continue();
      return;
    }
    const body = JSON.parse(request.postData() ?? "{}") as { apiKey?: string };
    const key = (body.apiKey ?? "").trim();
    if (!key.startsWith("rv_live_") && !key.startsWith("rv_test_")) {
      await route.fulfill({
        status: 400,
        contentType: "application/json",
        body: JSON.stringify({
          error: "ERR_AUTH_FORMAT",
          detail: "API key must start with rv_live_ or rv_test_",
        }),
      });
      return;
    }
    // The real handler writes iron-session; we set a dummy cookie that downstream
    // /api/* mocks will ignore. What matters for the UI is that the fetch() resolves 200
    // and router.push('/search') fires.
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: {
        "Set-Cookie": "rv_session=e2e-mock-session; Path=/; HttpOnly; SameSite=Lax",
      },
      body: JSON.stringify({ ok: true }),
    });
  });
}

/** Register a canned /api/search/facets response. */
export async function mockSearchFacets(
  page: Page,
  data: FacetResponse = DEFAULT_FACETS,
): Promise<void> {
  await page.route("**/api/search/facets", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(data),
    });
  });
}

/**
 * Register a canned /api/search/studies handler. The factory form lets a
 * spec inspect the request body and vary the response by filters.
 */
export async function mockSearchStudies(
  page: Page,
  factory: ((body: Record<string, unknown>) => SearchResponse) | SearchResponse = DEFAULT_SEARCH,
): Promise<void> {
  await page.route("**/api/search/studies", async (route: Route) => {
    const body = JSON.parse(route.request().postData() ?? "{}") as Record<string, unknown>;
    const payload = typeof factory === "function" ? factory(body) : factory;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(payload),
    });
  });
}

/**
 * Register a canned POST /api/orders handler that echoes back an order id
 * derived from the idempotency key. Shape follows dev-spec §7 D-3 (buyer_phase).
 */
export async function mockCreateOrder(page: Page, orderId = "ord_e2edemo01"): Promise<void> {
  await page.route("**/api/orders", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    const postData = JSON.parse(route.request().postData() ?? "{}") as {
      pseudo_study_uids?: string[];
    };
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({
        order_id: orderId,
        state: "queued",
        buyer_phase: "accepted",
        n_studies: postData.pseudo_study_uids?.length ?? 0,
        total_bytes: 0,
        submitted_at: new Date().toISOString(),
      }),
    });
  });
}

/** Register a canned GET /api/orders/{orderId} handler. */
export async function mockOrderDetail(
  page: Page,
  orderId: string,
  phase: "accepted" | "fetching_from_hospital" | "preparing_download" | "ready_to_download" | "completed" = "accepted",
): Promise<void> {
  await page.route(`**/api/orders/${orderId}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        order_id: orderId,
        state: phase === "accepted" ? "queued" : phase,
        buyer_phase: phase,
        n_studies: 3,
        total_bytes: 120 * 1024 * 1024,
        submitted_at: new Date().toISOString(),
        estimated_ready_at: new Date(Date.now() + 30 * 60_000).toISOString(),
      }),
    });
  });
}

/** Register a canned /api/hospital/stats response (dev-spec §7 D-2). */
export async function mockHospitalStats(
  page: Page,
  data: HospitalStatsResponse = DEFAULT_HOSPITAL_STATS,
): Promise<void> {
  await page.route("**/api/hospital/stats", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(data),
    });
  });
}

/** Register a canned /api/hospital/orders response. */
export async function mockHospitalOrders(
  page: Page,
  data: HospitalOrdersResponse = DEFAULT_HOSPITAL_ORDERS,
): Promise<void> {
  await page.route("**/api/hospital/orders*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(data),
    });
  });
}

/** Register a canned /api/hospital/audit response. */
export async function mockHospitalAudit(
  page: Page,
  data: HospitalAuditResponse = DEFAULT_HOSPITAL_AUDIT,
): Promise<void> {
  await page.route("**/api/hospital/audit*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(data),
    });
  });
}

/**
 * Safety net: refuse every other /api/* call. If a spec forgets to register
 * a mock for some endpoint, we want the test to fail loud, not silently fall
 * through to the real BFF (which would then try to reach the real upstream).
 *
 * Call this FIRST in beforeEach, then layer specific mocks on top. Playwright
 * tries handlers in reverse registration order so earlier ones win.
 */
export async function blockRealUpstream(page: Page): Promise<void> {
  await page.route("**/api/**", async (route) => {
    await route.fulfill({
      status: 599,
      contentType: "application/json",
      body: JSON.stringify({
        error: "ERR_E2E_UNMOCKED_ENDPOINT",
        detail: `Route ${route.request().url()} was not mocked by the spec. Register a handler in e2e/fixtures/mocks.ts.`,
      }),
    });
  });
}

// -- Default fixtures ---------------------------------------------------------

export const DEFAULT_FACETS: FacetResponse = {
  modality: [
    { value: "CT", count: 156 },
    { value: "MR", count: 82 },
    { value: "CR", count: 41 },
    { value: "MG", count: 12 },
  ],
  body_part: [
    { value: "CHEST", count: 103 },
    { value: "BRAIN", count: 58 },
    { value: "ABDOMEN", count: 34 },
    { value: "SPINE", count: 18 },
  ],
  sex: [
    { value: "M", count: 168 },
    { value: "F", count: 123 },
  ],
  manufacturer: [
    { value: "Siemens", count: 98 },
    { value: "GE", count: 74 },
  ],
};

export const DEFAULT_STUDIES: SearchStudy[] = [
  {
    pseudo_study_uid: "2.25.100000000000000000000000000001",
    modality: "CT",
    body_part: "CHEST",
    age_bucket: "50-60",
    sex: "M",
    n_instances: 412,
    total_bytes: 312 * 1024 * 1024,
    study_year: 2024,
    study_date_shifted: "2024-08-14",
    hospital_opaque_id: "a1b2c3d4e5f6a7b8",
  },
  {
    pseudo_study_uid: "2.25.100000000000000000000000000002",
    modality: "CT",
    body_part: "CHEST",
    age_bucket: "60-70",
    sex: "F",
    n_instances: 388,
    total_bytes: 295 * 1024 * 1024,
    study_year: 2024,
    study_date_shifted: "2024-05-02",
    hospital_opaque_id: "a1b2c3d4e5f6a7b8",
  },
  {
    pseudo_study_uid: "2.25.100000000000000000000000000003",
    modality: "CT",
    body_part: "CHEST",
    age_bucket: "70-80",
    sex: "M",
    n_instances: 522,
    total_bytes: 401 * 1024 * 1024,
    study_year: 2023,
    study_date_shifted: "2023-11-10",
    hospital_opaque_id: "b9c8d7e6f5a4b3c2",
  },
  {
    pseudo_study_uid: "2.25.100000000000000000000000000004",
    modality: "MR",
    body_part: "BRAIN",
    age_bucket: "40-50",
    sex: "M",
    n_instances: 162,
    total_bytes: 48 * 1024 * 1024,
    study_year: 2025,
    study_date_shifted: "2025-01-22",
    hospital_opaque_id: "b9c8d7e6f5a4b3c2",
  },
  {
    pseudo_study_uid: "2.25.100000000000000000000000000005",
    modality: "MR",
    body_part: "BRAIN",
    age_bucket: "50-60",
    sex: "F",
    n_instances: 178,
    total_bytes: 54 * 1024 * 1024,
    study_year: 2024,
    study_date_shifted: "2024-09-05",
    hospital_opaque_id: "a1b2c3d4e5f6a7b8",
  },
];

export const DEFAULT_SEARCH: SearchResponse = {
  items: DEFAULT_STUDIES,
  total: DEFAULT_STUDIES.length,
  next_cursor: null,
};

export function filterStudies(
  body: Record<string, unknown>,
  pool: SearchStudy[] = DEFAULT_STUDIES,
): SearchResponse {
  // v0.2 SearchRequest schema (FR-INF-8/9): `modality` / `body_part` / etc.
  // We also accept the legacy `modalities` / `body_parts` for back-compat
  // with any older test that hasn't been migrated yet.
  const modalities = Array.isArray(body.modality)
    ? (body.modality as string[])
    : Array.isArray(body.modalities)
      ? (body.modalities as string[])
      : [];
  const bodyParts = Array.isArray(body.body_part)
    ? (body.body_part as string[])
    : Array.isArray(body.body_parts)
      ? (body.body_parts as string[])
      : [];
  const filtered = pool.filter((s) => {
    if (modalities.length && (!s.modality || !modalities.includes(s.modality)))
      return false;
    if (bodyParts.length && (!s.body_part || !bodyParts.includes(s.body_part)))
      return false;
    return true;
  });
  return { items: filtered, total: filtered.length, next_cursor: null };
}

export type HospitalStatsResponse = {
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

export const DEFAULT_HOSPITAL_STATS: HospitalStatsResponse = {
  hospital_id: "HOSP-001",
  studies: {
    today: 42,
    cumulative: 12_478,
    monthly_12m: [
      { year_month: "2025-05", count: 820 },
      { year_month: "2025-06", count: 910 },
      { year_month: "2025-07", count: 1030 },
      { year_month: "2025-08", count: 980 },
      { year_month: "2025-09", count: 1100 },
      { year_month: "2025-10", count: 1180 },
      { year_month: "2025-11", count: 1020 },
      { year_month: "2025-12", count: 1140 },
      { year_month: "2026-01", count: 1205 },
      { year_month: "2026-02", count: 1098 },
      { year_month: "2026-03", count: 1250 },
      { year_month: "2026-04", count: 745 },
    ],
  },
  gateway_health: {
    status: "online",
    last_sync_at: new Date(Date.now() - 3 * 60_000).toISOString(),
    last_sync_delta_seconds: 180,
  },
  modality_distribution: [
    { modality: "CT", count: 5_102 },
    { modality: "MR", count: 3_014 },
    { modality: "CR", count: 2_511 },
  ],
};

export type HospitalOrdersResponse = {
  orders: {
    order_id_masked: string;
    n_studies: number;
    phase: string;
    submitted_at: string;
    delivered_at: string | null;
  }[];
};

export const DEFAULT_HOSPITAL_ORDERS: HospitalOrdersResponse = {
  orders: [
    {
      order_id_masked: "ord_5a3f",
      n_studies: 12,
      phase: "completed",
      submitted_at: new Date(Date.now() - 3 * 3600_000).toISOString(),
      delivered_at: new Date(Date.now() - 2 * 3600_000).toISOString(),
    },
    {
      order_id_masked: "ord_7c2e",
      n_studies: 24,
      phase: "preparing_download",
      submitted_at: new Date(Date.now() - 15 * 60_000).toISOString(),
      delivered_at: null,
    },
    {
      order_id_masked: "ord_a1b2",
      n_studies: 8,
      phase: "accepted",
      submitted_at: new Date(Date.now() - 5 * 60_000).toISOString(),
      delivered_at: null,
    },
  ],
};

export type HospitalAuditResponse = {
  events: {
    ts: string;
    event_type: string;
    hash_short: string;
    detail_code: string | null;
  }[];
};

export const DEFAULT_HOSPITAL_AUDIT: HospitalAuditResponse = {
  events: [
    {
      ts: new Date(Date.now() - 2 * 60_000).toISOString(),
      event_type: "ingest.accepted",
      hash_short: "3f4a9b12",
      detail_code: null,
    },
    {
      ts: new Date(Date.now() - 5 * 60_000).toISOString(),
      event_type: "upload.completed",
      hash_short: "a8c2d1ff",
      detail_code: null,
    },
    {
      ts: new Date(Date.now() - 12 * 60_000).toISOString(),
      event_type: "anchor.recorded",
      hash_short: "7e2b8840",
      detail_code: null,
    },
    {
      ts: new Date(Date.now() - 25 * 60_000).toISOString(),
      event_type: "order.delivered",
      hash_short: "c3ae1177",
      detail_code: null,
    },
  ],
};
