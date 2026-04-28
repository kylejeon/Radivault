/**
 * Barrel exports for study-detail v3 components.
 *
 * Mockup source-of-truth: docs/specs/mockups/buyer-ux-v2/v3/study-detail.html
 * + styles.css. CSS classes live in web/portal/src/app/globals.css under the
 * `.rv-detail-*` / `.rv-quality-*` / `.rv-viewer-*` / `.rv-deid-*` /
 * `.rv-compliance-collapse` namespaces.
 */

export { QualityMetricsCard } from "./QualityMetricsCard";
export type { QualityMetricsCardProps } from "./QualityMetricsCard";

export { MetaCard } from "./MetaCard";
export type { MetaCardProps, MetaRow } from "./MetaCard";

export { SeriesMiniCardList } from "./SeriesMiniCardList";
export type {
  SeriesMiniCardListProps,
  SeriesMiniItem,
} from "./SeriesMiniCardList";

export { LongitudinalTimeline } from "./LongitudinalTimeline";
export type {
  LongitudinalTimelineProps,
  TimelineStep,
  TimelineStepState,
} from "./LongitudinalTimeline";

export { DeIDStepper } from "./DeIDStepper";
export type { DeIDStepperProps, DeIDStage } from "./DeIDStepper";

export { ComplianceCollapse } from "./ComplianceCollapse";
export type { ComplianceCollapseProps } from "./ComplianceCollapse";

export { StudyDetailSubBar } from "./StudyDetailSubBar";
export type { StudyDetailSubBarProps } from "./StudyDetailSubBar";

export { ViewerPaneV3 } from "./ViewerPaneV3";
export type { ViewerPaneV3Props } from "./ViewerPaneV3";
