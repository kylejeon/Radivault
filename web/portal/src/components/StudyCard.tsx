import clsx from "clsx";
import { ModalityBadge } from "@/components/ModalityBadge";

export type StudyCardProps = {
  pseudoStudyUid: string;
  modality: string | null;
  bodyPart: string | null;
  nInstances: number;
  sizeMb: number;
  studyYear: number | null;
  selected?: boolean;
  onToggle?: () => void;
};

/**
 * StudyCard — result row in the Search 3-pane (design-spec §3.4).
 *
 * No thumbnails (dev-spec §0.2-1). The modality badge doubles as the visual
 * anchor. Truncating UIDs to their last 8 chars is a design-spec §3.4
 * decision and matches the buyer CLI pattern.
 */
export function StudyCard({
  pseudoStudyUid,
  modality,
  bodyPart,
  nInstances,
  sizeMb,
  studyYear,
  selected,
  onToggle,
}: StudyCardProps) {
  const short = pseudoStudyUid.slice(-8);
  return (
    <div
      className={clsx(
        "card flex items-center gap-4 p-4",
        selected ? "ring-2 ring-primary" : "",
      )}
    >
      <input
        type="checkbox"
        checked={selected ?? false}
        onChange={onToggle}
        aria-label={`Select study ${short}`}
        className="size-4"
      />
      <ModalityBadge modality={modality} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <code className="font-mono text-sm text-ink" title={pseudoStudyUid}>
            …{short}
          </code>
          {bodyPart ? (
            <span className="text-xs text-ink-muted">{bodyPart}</span>
          ) : null}
        </div>
        <div className="mt-1 flex items-center gap-4 text-xs text-ink-subtle">
          <span>{nInstances.toLocaleString()} instances</span>
          <span>{sizeMb.toFixed(1)} MB</span>
          {studyYear !== null ? <span>{studyYear}</span> : null}
        </div>
      </div>
    </div>
  );
}
