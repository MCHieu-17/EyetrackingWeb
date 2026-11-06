import { apiFetch } from "./client";

export interface AoiDefinition {
  id: string;
  code: string;
  name: string;
  parentId: string | null;
  geometry: Record<string, unknown>;
}

export interface AoiSet {
  id: string;
  scope: "slide" | "ui";
  slideVersionId: string | null;
  uiSchemaVersion: string | null;
  revision: number;
  state: "draft" | "published" | "archived";
  createdBy: string;
  createdAt: string;
  publishedAt: string | null;
  definitions: AoiDefinition[];
}

export interface AoiDefinitionInput {
  code: string;
  name: string;
  parentId?: string | null;
  geometry: Record<string, unknown>;
}

export interface AoiSetInput {
  scope: "slide" | "ui";
  slideVersionId?: string | null;
  uiSchemaVersion?: string | null;
  definitions: AoiDefinitionInput[];
}

export interface AoiRect {
  code: string;
  xMin: number;
  yMin: number;
  xMax: number;
  yMax: number;
}

export interface AoiLayoutSnapshot {
  id: string;
  presentationId: string;
  layoutGeneration: number;
  capturedAt: string;
}

export interface ContentPresentation {
  id: string;
  sessionId: string;
  lessonVersionSlideId: string | null;
  surface: "lesson" | "quiz";
  sequenceNo: number;
  startedAt: string;
}

export interface AnalysisRun {
  id: string;
  sessionId: string;
  aoiSetId: string;
  fromTime: string;
  toTime: string;
  batchWatermark: string | null;
  algorithmVersion: string;
  status: "pending" | "running" | "completed" | "failed";
  error: string | null;
  createdAt: string;
  completedAt: string | null;
}

export interface PresentationMetric {
  presentationId: string;
  algorithmVersion: string;
  batchWatermark: string | null;
  sampleCount: number;
  onSlideCount: number;
  dwellMs: number;
  fixationCount: number;
  heatmapGrid: number[][];
  computedAt: string;
}

export interface AnalysisRunResult {
  run: AnalysisRun;
  hitCount: number;
  metrics: PresentationMetric[];
}

export function fetchAoiSets(params: {
  scope?: "slide" | "ui";
  slideVersionId?: string;
  uiSchemaVersion?: string;
  state?: "draft" | "published" | "archived";
} = {}): Promise<AoiSet[]> {
  return apiFetch<AoiSet[]>("/api/aoi-sets", { params });
}

export function createAoiSet(input: AoiSetInput): Promise<AoiSet> {
  return apiFetch<AoiSet>("/api/aoi-sets", { method: "POST", body: input });
}

export function updateAoiSet(
  id: string,
  definitions: AoiDefinitionInput[],
): Promise<AoiSet> {
  return apiFetch<AoiSet>(`/api/aoi-sets/${id}`, {
    method: "PATCH",
    body: { definitions },
  });
}

export function publishAoiSet(id: string): Promise<{ ok: boolean; id: string; state: string }> {
  return apiFetch(`/api/aoi-sets/${id}/publish`, { method: "POST" });
}

export function createAnalysisRun(
  input: {
    sessionId: string;
    aoiSetId: string;
    fromTime: string;
    toTime: string;
    algorithmVersion?: string;
    config?: Record<string, unknown>;
  },
  idempotencyKey?: string,
): Promise<AnalysisRunResult> {
  return apiFetch<AnalysisRunResult>("/api/analysis-runs", {
    method: "POST",
    body: input,
    headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : undefined,
  });
}

export function fetchAnalysisRun(id: string): Promise<AnalysisRunResult> {
  return apiFetch<AnalysisRunResult>(`/api/analysis-runs/${id}`);
}

export function analysisExportUrl(id: string): string {
  return `/api/analysis-runs/${id}/export`;
}

export function rebuildAoiHits(input: {
  courseId: string;
  fromTime?: string;
  toTime?: string;
  algorithmVersion?: string;
}): Promise<{ ok: boolean; runs: number; completed: number; failed: number }> {
  return apiFetch("/api/aoi/rebuild", {
    method: "POST",
    body: {
      courseId: input.courseId,
      fromTime: input.fromTime,
      toTime: input.toTime,
      algorithmVersion: input.algorithmVersion,
    },
  });
}

export function createPresentation(
  sessionId: string,
  input: {
    lessonVersionSlideId?: string | null;
    surface: "lesson" | "quiz";
    sequenceNo: number;
  },
): Promise<ContentPresentation> {
  return apiFetch<ContentPresentation>(
    `/api/learning-sessions/${sessionId}/presentations`,
    { method: "POST", body: input },
  );
}

export function createPresentationLayout(
  presentationId: string,
  input: {
    sequenceNo: number;
    layoutGeneration: number;
    imageTransform?: Record<string, unknown>;
    rects: AoiRect[];
  },
): Promise<AoiLayoutSnapshot> {
  return apiFetch<AoiLayoutSnapshot>(
    `/api/presentations/${presentationId}/layouts`,
    { method: "POST", body: input },
  );
}
