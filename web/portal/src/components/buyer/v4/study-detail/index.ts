/**
 * Barrel exports for study-detail v4 components (DICOM Viewer v2).
 *
 * Mockup source-of-truth: docs/specs/mockups/buyer-ux-v2/v4/study-detail.html
 * + styles.css.
 */

export { ViewerPaneV4 } from "./ViewerPaneV4";
export type { ViewerPaneV4Props } from "./ViewerPaneV4";

export { SeriesPicker } from "./SeriesPicker";
export type { SeriesPickerProps } from "./SeriesPicker";

export { ViewerToolbar } from "./ViewerToolbar";
export type { ViewerToolbarProps, ToolbarTool } from "./ViewerToolbar";

export { ViewerCanvas, wlFilter, clampZoom, clampWindow } from "./ViewerCanvas";
export type { ViewerCanvasProps, Pan } from "./ViewerCanvas";
export {
  ZOOM_DEFAULT,
  ZOOM_MIN,
  ZOOM_MAX,
  PAN_DEFAULT,
  WW_DEFAULT,
  WL_DEFAULT,
  WW_MIN,
  WW_MAX,
  WL_MIN,
  WL_MAX,
} from "./ViewerCanvas";

export { ViewerOverlay } from "./ViewerOverlay";
export type { ViewerOverlayProps } from "./ViewerOverlay";

export { ViewerWatermark } from "./ViewerWatermark";

export { PresetMenu, PRESETS } from "./PresetMenu";
export type { PresetMenuProps, PresetSpec, PresetId } from "./PresetMenu";

export { SeriesMiniCardListV4 } from "./SeriesMiniCardListV4";
export type {
  SeriesMiniCardListV4Props,
  SeriesMiniItemV4,
} from "./SeriesMiniCardListV4";
