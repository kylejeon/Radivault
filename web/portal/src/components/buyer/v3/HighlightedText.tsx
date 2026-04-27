"use client";

/**
 * <HighlightedText> — text-search-description FR-TS-9 / design-spec §8.
 *
 * Renders the server-side ``ts_headline`` snippet (e.g. ``BRAIN <mark>MR</mark>``)
 * safely. Two reasons we hand-roll a whitelist parser instead of pulling in
 * DOMPurify:
 *
 * 1. The ``<mark>`` whitelist is the *entire* allowed tag set. A bespoke
 *    splitter is ~30 lines, easy to audit, and adds zero runtime weight.
 * 2. The ts_headline output is already HTML-escaped by Postgres on every
 *    field except the StartSel/StopSel pair we explicitly opt into. The
 *    parser here is the second-line defence — it strips ANY tag that isn't
 *    the literal ``<mark>`` or ``</mark>``, plus all attributes. Anything
 *    else lands as plain text.
 */

import type { CSSProperties } from "react";

export type HighlightedTextProps = {
  /** Server-rendered ts_headline HTML — null when q is unused. */
  html: string | null | undefined;
  /** Plain-text fallback rendered when ``html`` is null/empty. */
  fallback: string | null | undefined;
  /**
   * User's raw search query. When set, highlights only the *typed prefix*
   * inside each matching word ("bra" → BRA in <mark>BRA</mark>IN), instead
   * of letting Postgres ts_headline wrap the entire matched lexeme. Takes
   * precedence over ``html``.
   */
  query?: string | null;
  /** Optional truncation length (default 200). */
  maxLength?: number;
  className?: string;
  style?: CSSProperties;
};

const TOKEN_RE = /[a-zA-Z0-9]+/g;

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Wrap typed prefixes inside ``text`` with ``<mark>`` tags. Sanitised via
 * ``escapeHtml`` first so the only HTML in the output is the literal mark
 * pair. Matches are case-insensitive prefix-anywhere — "bra" hits "BRAIN",
 * "ABRASION", but not in the middle of a longer token's body. Multiple
 * tokens unify into one alternation with longest-first ordering so "brain"
 * wins over "br" inside the same word.
 */
function buildPrefixHighlight(text: string, query: string): string {
  const tokens = (query.match(TOKEN_RE) ?? []).filter((t) => t.length > 0);
  if (tokens.length === 0) return escapeHtml(text);
  // Longest first → matches "brain" over "br" if user typed both.
  const ordered = [...new Set(tokens.map((t) => t.toLowerCase()))].sort(
    (a, b) => b.length - a.length,
  );
  const pattern = new RegExp(
    `(${ordered.map(escapeRegExp).join("|")})[a-zA-Z0-9]*`,
    "gi",
  );
  // Walk matches and rebuild with escaped text + <mark> for prefix only.
  let out = "";
  let last = 0;
  for (const m of text.matchAll(pattern)) {
    const start = m.index ?? 0;
    const matched = m[0];
    const prefix = m[1];
    out += escapeHtml(text.slice(last, start));
    out += `<mark>${escapeHtml(prefix)}</mark>`;
    out += escapeHtml(matched.slice(prefix.length));
    last = start + matched.length;
  }
  out += escapeHtml(text.slice(last));
  return out;
}

const MARK_OPEN = /<mark>/gi;
const MARK_CLOSE = /<\/mark>/gi;

// Anything that even *looks* like another tag — including attributes,
// scripts, comments — gets turned into text.
const ANY_TAG = /<[^>]*>/g;

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/**
 * Sanitise ``raw`` so the returned string only ever contains escaped text +
 * exact ``<mark>`` / ``</mark>`` tag pairs. Re-orderings that happen to drop
 * a closing tag are tolerated — the resulting <mark> would naturally close
 * at the next render boundary.
 */
function sanitiseMarkOnly(raw: string): string {
  // 1. Stash <mark> tags behind ASCII placeholders no host string would
  //    contain (NUL is forbidden in well-formed input).
  const OPEN_TOKEN = "\x00rvm0\x00";
  const CLOSE_TOKEN = "\x00rvm1\x00";
  let staged = raw.replace(MARK_OPEN, OPEN_TOKEN).replace(MARK_CLOSE, CLOSE_TOKEN);
  // 2. Strip every other tag-like substring.
  staged = staged.replace(ANY_TAG, "");
  // 3. Escape — this turns everything that survives into plain text.
  staged = escapeHtml(staged);
  // 4. Reinstate the ``<mark>`` whitelist.
  return staged
    .split(OPEN_TOKEN)
    .join("<mark>")
    .split(CLOSE_TOKEN)
    .join("</mark>");
}

export function HighlightedText({
  html,
  fallback,
  query,
  maxLength = 200,
  className,
  style,
}: HighlightedTextProps): JSX.Element {
  const fallbackText = fallback ?? "";

  // Client-side prefix highlight wins over server snippet when query present.
  // This satisfies Kyle's UX rule: "bra" must highlight BRA inside BRAIN, not
  // the full word — Postgres ts_headline only wraps at lexeme boundaries.
  if (query && query.trim().length > 0) {
    const truncated = truncate(fallbackText, maxLength);
    const safe = buildPrefixHighlight(truncated, query.trim());
    return (
      <span
        className={className}
        style={style}
        // ``buildPrefixHighlight`` escapes everything and only emits literal
        // <mark>...</mark> wrappers — no other tags or attributes possible.
        dangerouslySetInnerHTML={{ __html: safe }}
      />
    );
  }

  if (!html) {
    return (
      <span className={className} style={style}>
        {truncate(fallbackText, maxLength)}
      </span>
    );
  }

  // ts_headline can occasionally emit an empty string when q matched no token
  // in this row's covered fields. Render the fallback in that case so the
  // cell isn't blank.
  const trimmed = html.trim();
  if (!trimmed) {
    return (
      <span className={className} style={style}>
        {truncate(fallbackText, maxLength)}
      </span>
    );
  }

  const truncated = truncate(trimmed, maxLength);
  const safe = sanitiseMarkOnly(truncated);
  return (
    <span
      className={className}
      style={style}
      // The sanitiser above guarantees only escaped text + literal <mark> tags
      // reach the DOM. No event handlers, no other tags, no attributes.
      dangerouslySetInnerHTML={{ __html: safe }}
    />
  );
}

function truncate(s: string, max: number): string {
  if (s.length <= max) return s;
  return `${s.slice(0, max - 1)}…`;
}
