/**
 * Thin upstream fetch wrapper used by BFF route handlers.
 *
 * - Adds the appropriate Bearer for the target service.
 * - Propagates X-Request-Id to upstream and echoes the response ID back.
 * - Honours a simple 5s timeout so the portal never hangs on a dead service.
 * - On failure returns a normalised error envelope matching design-spec §7.
 */

import { env } from "@/lib/env";
import { randomUUID } from "node:crypto";

export type UpstreamResult<T> =
  | { ok: true; status: number; data: T; requestId: string }
  | {
      ok: false;
      status: number;
      code: string;
      detail: string;
      requestId: string;
      retryAfter?: number;
    };

const DEFAULT_TIMEOUT_MS = 5_000;

async function fetchWithTimeout(
  url: string,
  init: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

export async function upstreamFetch<T = unknown>(
  base: string,
  path: string,
  init: {
    method?: string;
    bearer?: string;
    body?: unknown;
    query?: Record<string, string | number | undefined>;
    timeoutMs?: number;
    requestId?: string;
    headers?: Record<string, string>;
  } = {},
): Promise<UpstreamResult<T>> {
  const query = init.query
    ? "?" +
      Object.entries(init.query)
        .filter(([, v]) => v !== undefined && v !== null && v !== "")
        .map(
          ([k, v]) =>
            `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`,
        )
        .join("&")
    : "";
  const url = `${base.replace(/\/$/, "")}${path}${query}`;
  const requestId = init.requestId ?? randomUUID();
  const headers: Record<string, string> = {
    Accept: "application/json",
    "X-Request-Id": requestId,
    ...(init.headers ?? {}),
  };
  if (init.bearer) headers["Authorization"] = `Bearer ${init.bearer}`;
  if (init.body !== undefined) headers["Content-Type"] = "application/json";

  try {
    const res = await fetchWithTimeout(
      url,
      {
        method: init.method ?? "GET",
        headers,
        body: init.body === undefined ? undefined : JSON.stringify(init.body),
      },
      init.timeoutMs ?? DEFAULT_TIMEOUT_MS,
    );
    const echoedId = res.headers.get("X-Request-Id") ?? requestId;
    const retryAfter = res.headers.get("Retry-After");
    const parsedRetryAfter = retryAfter ? Number.parseInt(retryAfter, 10) : undefined;
    const contentType = res.headers.get("Content-Type") ?? "";
    const text = await res.text();
    const payload = contentType.includes("application/json") && text
      ? JSON.parse(text)
      : text;
    if (!res.ok) {
      const code =
        typeof payload === "object" && payload && "error" in payload
          ? String((payload as Record<string, unknown>).error)
          : `ERR_HTTP_${res.status}`;
      const detail =
        typeof payload === "object" && payload && "detail" in payload
          ? String((payload as Record<string, unknown>).detail)
          : typeof payload === "string"
            ? payload
            : "Upstream error";
      return {
        ok: false,
        status: res.status,
        code,
        detail,
        requestId: echoedId,
        retryAfter: parsedRetryAfter,
      };
    }
    return { ok: true, status: res.status, data: payload as T, requestId: echoedId };
  } catch (err) {
    return {
      ok: false,
      status: 504,
      code: "ERR_UPSTREAM_UNAVAILABLE",
      detail: err instanceof Error ? err.message : String(err),
      requestId,
    };
  }
}

export const bases = {
  get central() {
    return env.centralIngestUrl;
  },
  get search() {
    return env.searchUrl;
  },
  get fulfillment() {
    return env.fulfillmentUrl;
  },
};
