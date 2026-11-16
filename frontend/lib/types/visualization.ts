// DTO cho tab Trực quan hoá của giáo viên. Khớp backend
// app/schemas/analytics.py (CamelModel).

export interface ReplayRect {
  xMin: number;
  yMin: number;
  xMax: number;
  yMax: number;
}

interface ReplayTransformRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

interface ReplaySlideAoi {
  code: string;
  name: string;
  analysisLabel: string | null;
  kind: string;
  isContainer: boolean;
  isActive: boolean;
  rects: ReplayRect[];
}

interface ReplayUiRegion {
  code: string;
  name: string;
  kind: string;
  label?: string | null;
  isActive: boolean;
  rects: ReplayRect[];
}

export interface ReplayLayout {
  id: string;
  layoutNo: number;
  slideRect: Partial<ReplayTransformRect>;
  capturedAt: string;
  uiRegions: ReplayUiRegion[];
}

interface ReplayViewport {
  width: number | null;
  height: number | null;
}

export interface ReplayAoiStat {
  label: string;
  name: string;
  domain: "slide" | "ui";
  durationMs: number;
  sampleCount: number;
}

export interface ReplayView {
  contentViewId: string;
  sequenceNo: number;
  surface: "lesson" | "quiz";
  sessionId: string;
  lessonId: string;
  lessonTitle: string;
  lessonKind: string;
  slideId: string | null;
  slideTitle: string | null;
  pageNumber: number | null;
  pdfUrl: string | null;
  startedAt: string;
  endedAt: string | null;
  firstSampleAt: string | null;
  lastSampleAt: string | null;
  sampleCount: number;
  okSampleCount: number;
  gazeCount: number;
  onSlideGazeCount: number;
  trackedDurationMs: number;
  /** Thời gian thực tế trên slide (wall time), khác với span của sample. */
  dwellMs: number;
  /** dwellMs >= ngưỡng CONTENT_VIEW_MIN_DWELL_MS. */
  counted: boolean;
  analysisStatus: string;
  analysisVersion: string;
  viewport: ReplayViewport;
  slideAois: ReplaySlideAoi[];
  layouts: ReplayLayout[];
  aoiStats: ReplayAoiStat[];
}

interface ReplayStudent {
  id: string;
  name: string;
  code: string;
  email: string | null;
  enrollmentStatus: string;
}

interface ReplayCourse {
  id: string;
  title: string;
}

export interface VisitReplay {
  visit: {
    visitId: string;
    enrollmentId: string;
    studentId: string;
    courseId: string;
    startedAt: string;
    endedAt: string | null;
    status: string;
    lessonSessionCount: number;
    contentViewCount: number;
    gazeCount: number;
    onSlideGazeCount: number;
    trackedDurationMs: number;
    fixationCount: number;
    minDwellMs: number;
    shortViewCount: number;
  };
  student: ReplayStudent;
  course: ReplayCourse;
  views: ReplayView[];
  uiAois: {
    code: string;
    name: string;
    label?: string | null;
    kind: string;
    isActive: boolean;
  }[];
}

export interface ReplaySample {
  id: number;
  offsetMs: number;
  eventTime: string;
  sequence: number;
  layoutId: string | null;
  status: string;
  viewportX: number | null;
  viewportY: number | null;
  slideX: number | null;
  slideY: number | null;
  aoiLabel: string | null;
  qualityFlags: Record<string, unknown>;
}

export interface ReplaySampleCursor {
  afterTime: string;
  afterId: number;
}

export interface ReplaySamplesPage {
  contentViewId: string;
  samples: ReplaySample[];
  nextCursor: ReplaySampleCursor | null;
}

export type SummaryScope = "visit" | "student" | "cohort";
export type SummarySurface = "all" | "lesson" | "quiz";

export interface AoiSummaryQuery {
  studentIds?: string[];
  visitIds?: string[];
  lessonIds?: string[];
  from?: string;
  to?: string;
  surface?: SummarySurface;
  includeDropped?: boolean;
  /** Mặc định backend là true (tính cả lượt xem ngắn). */
  includeShort?: boolean;
}

export interface AoiSummaryTotals {
  visitCount: number;
  studentCount: number;
  contentViewCount: number;
  gazeSampleCount: number;
  onSlideGazeCount: number;
  trackedDurationMs: number;
  labeledDurationMs: number;
  slideDurationMs: number;
  uiDurationMs: number;
  unmappedDurationMs: number;
  unlabeledDurationMs: number;
}

export interface AoiSummaryAoi {
  label: string;
  name: string;
  domain: "slide" | "ui";
  durationMs: number;
  sampleCount: number;
  share: number;
  studentCount: number;
  slideCount: number;
  mixedSlides: boolean;
  isUnlabeled: boolean;
}

export interface AoiSummaryLesson {
  lessonId: string;
  lessonTitle: string;
  lessonKind: string;
  durationMs: number;
  sampleCount: number;
  aois: AoiSummaryAoi[];
}

interface AoiSummarySlide {
  slideId: string;
  slideTitle: string;
  lessonId: string;
  lessonTitle: string;
  pageNumber: number | null;
  durationMs: number;
  sampleCount: number;
  aois: AoiSummaryAoi[];
}

export interface AoiSummaryStudent {
  studentId: string;
  studentName: string;
  studentCode: string;
  enrollmentStatus: string;
  durationMs: number;
  sampleCount: number;
  aois: AoiSummaryAoi[];
}

export interface AoiSummaryVisit {
  visitId: string;
  studentId: string;
  studentName: string;
  startedAt: string;
  durationMs: number;
  trackedDurationMs: number;
  slideDurationMs: number;
  uiDurationMs: number;
  unlabeledDurationMs: number;
  sampleCount: number;
}

export interface AoiSummary {
  totals: AoiSummaryTotals;
  byAoi: AoiSummaryAoi[];
  byLesson: AoiSummaryLesson[];
  bySlide: AoiSummarySlide[];
  byStudent: AoiSummaryStudent[];
  byVisit: AoiSummaryVisit[];
  meta: {
    staleViewCount: number;
    analysisVersion: string;
    includeDropped: boolean;
    /** Optional để tương thích backend cũ/chưa triển khai. */
    includeShort?: boolean;
    shortViewCount?: number;
    minDwellMs?: number;
  };
}

export interface AoiHeatmapQuery extends AoiSummaryQuery {
  slideId: string;
}

export interface AoiHeatmap {
  slide: {
    id: string;
    title: string;
    pageNumber: number;
    pdfUrl: string | null;
    lessonTitle: string;
  };
  grid: number[][];
  max: number;
  onSlideSampleCount: number;
}
