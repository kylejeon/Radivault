/**
 * format.ts — shared formatters for the hospital console (§17).
 *
 * Kept tiny on purpose. Heavier i18n / number libs are intentionally
 * avoided so the hospital tiles stay below the 1.6 kB (gzipped) budget
 * each (§17 narrative).
 */

const KST_TIMEZONE = "Asia/Seoul";

export function formatBytes(bytes: number, fractionDigits = 1): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB", "PB"];
  let i = 0;
  let n = bytes;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i++;
  }
  // Drop the decimal for B/KB to keep the tiles compact.
  const digits = i <= 1 ? 0 : fractionDigits;
  return `${n.toFixed(digits)} ${units[i]}`;
}

export function formatKstTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: KST_TIMEZONE,
    hour12: false,
  });
}

export function formatKstDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  // 2026-04-25 14:23 (KST 24h, no seconds — matches §18.2 column copy)
  const y = d.toLocaleString("ko-KR", { year: "numeric", timeZone: KST_TIMEZONE });
  const mo = d.toLocaleString("ko-KR", { month: "2-digit", timeZone: KST_TIMEZONE });
  const da = d.toLocaleString("ko-KR", { day: "2-digit", timeZone: KST_TIMEZONE });
  const hm = d.toLocaleString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: KST_TIMEZONE,
    hour12: false,
  });
  return `${y.replace(/[^0-9]/g, "")}-${mo.replace(/[^0-9]/g, "").padStart(2, "0")}-${da.replace(/[^0-9]/g, "").padStart(2, "0")} ${hm}`;
}

export function formatKstDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone: KST_TIMEZONE,
  });
}

/**
 * Korean Won — K-13 decision: ₩ 150,000 form (full-spell with currency
 * symbol). Implemented as a plain prefix + Intl number to avoid
 * `currency: "KRW"` injecting "KRW" or "원" depending on the runtime ICU
 * version (Node 20 vs 22 differ).
 */
export function formatKrw(amount: number): string {
  if (!Number.isFinite(amount)) return "₩ —";
  return `₩ ${Math.round(amount).toLocaleString("ko-KR")}`;
}

/**
 * Returns "n분 전" / "n시간 전" / "어제" relative copy from now.
 * Used by Gateway HB and Audit chain.
 */
export function formatRelativeKo(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  if (!Number.isFinite(t)) return "—";
  const deltaSec = Math.max(0, Math.floor((now - t) / 1000));
  if (deltaSec < 60) return "방금 전";
  if (deltaSec < 3600) return `${Math.floor(deltaSec / 60)}분 전`;
  if (deltaSec < 86400) return `${Math.floor(deltaSec / 3600)}시간 전`;
  return `${Math.floor(deltaSec / 86400)}일 전`;
}
