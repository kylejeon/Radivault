/*
 * In-memory token-bucket rate limiter (HIGH-1 supporting module for
 * /api/contact). Lives outside the route file because Next.js 14 forbids
 * non-handler exports from app route files.
 *
 * The bucket is per-process; multi-instance deploys defeat it. v0.1.1
 * lifts the bucket into Redis.
 */

type Bucket = { count: number; resetAt: number };

export type RateLimiter = {
  check(key: string): { ok: true } | { ok: false; retryAfterSeconds: number };
  reset(): void;
};

export function makeRateLimiter({
  max,
  windowMs,
  now = () => Date.now(),
}: {
  max: number;
  windowMs: number;
  now?: () => number;
}): RateLimiter {
  const buckets = new Map<string, Bucket>();
  return {
    check(key: string) {
      const t = now();
      const existing = buckets.get(key);
      if (!existing || existing.resetAt < t) {
        buckets.set(key, { count: 1, resetAt: t + windowMs });
        return { ok: true };
      }
      if (existing.count >= max) {
        return {
          ok: false,
          retryAfterSeconds: Math.max(1, Math.ceil((existing.resetAt - t) / 1000)),
        };
      }
      existing.count += 1;
      return { ok: true };
    },
    reset() {
      buckets.clear();
    },
  };
}

// Singleton for the contact route. Tests call contactRateLimiter.reset()
// directly between cases.
export const contactRateLimiter = makeRateLimiter({
  max: 5,
  windowMs: 60_000,
});
