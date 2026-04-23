/**
 * KoreaHeatmap — SVG placeholder (dev-spec §0.2-13).
 *
 * v0.1 ships a static silhouette of South Korea with 1-2 highlighted points
 * (demo hospitals). The tooltip/drilldown story lands in v0.2; we keep the
 * API shape stable so callers can pass N regions later without a refactor.
 *
 * The path data is intentionally coarse (~60 control points) — it's a
 * silhouette suitable for a 280x220 card, not a production map.
 */
export type Region = {
  id: string;
  name: string; // localised label (e.g. "서울")
  x: number; // 0-100 percent of the viewBox width
  y: number; // 0-100 percent of the viewBox height
  active?: boolean;
};

export function KoreaHeatmap({ regions }: { regions: Region[] }) {
  return (
    <svg
      viewBox="0 0 100 120"
      role="img"
      aria-label="기여 지역 지도"
      className="h-full w-full"
    >
      {/* Very coarse silhouette of the Korean peninsula (south-only focus). */}
      <path
        d="M44,8 L52,6 L60,10 L66,18 L70,28 L72,40 L78,46 L80,54 L82,66 L78,76 L70,82 L66,92 L62,100 L54,106 L46,108 L40,104 L34,98 L28,90 L24,80 L22,70 L18,60 L16,50 L18,40 L22,30 L28,22 L34,16 Z"
        className="fill-surface-muted stroke-surface-border"
        strokeWidth="0.6"
      />
      {regions.map((r) => (
        <g key={r.id}>
          <circle
            cx={r.x}
            cy={r.y}
            r={r.active ? 2.4 : 1.8}
            className={r.active ? "fill-primary" : "fill-ink-subtle"}
            opacity={r.active ? 1 : 0.6}
          />
          <text
            x={r.x + 3}
            y={r.y + 1.2}
            className="fill-ink text-[3px] font-medium"
            style={{ fontSize: "3px" }}
          >
            {r.name}
          </text>
        </g>
      ))}
    </svg>
  );
}
