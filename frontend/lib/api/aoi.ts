import { apiFetch } from "./client";

type AoiKind =
  | "text"
  | "image"
  | "table"
  | "drawing"
  | "custom"
  | "ui"
  | "system";

export interface AoiDefinition {
  id: string;
  code: string;
  name: string;
  parentId: string | null;
  geometry: Record<string, unknown>;
  isContainer: boolean;
  kind: AoiKind;
  isActive: boolean;
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
  isContainer?: boolean;
  kind?: AoiKind;
  isActive?: boolean;
}

interface AoiSetSaveInput {
  definitions: AoiDefinitionInput[];
  expectedRevision?: number;
}

export interface AoiUiComponent {
  code: string;
  name: string;
}

export interface AoiRect {
  code: string;
  xMin: number;
  yMin: number;
  xMax: number;
  yMax: number;
}

interface AoiLayoutSnapshot {
  id: string;
  presentationId: string;
  layoutGeneration: number;
  capturedAt: string;
}

interface ContentPresentation {
  id: string;
  sessionId: string;
  lessonVersionSlideId: string | null;
  surface: "lesson" | "quiz";
  sequenceNo: number;
  startedAt: string;
}

export function fetchAoiSets(params: {
  scope?: "slide" | "ui";
  slideVersionId?: string;
  uiSchemaVersion?: string;
  state?: "draft" | "published" | "archived";
} = {}): Promise<AoiSet[]> {
  return apiFetch<AoiSet[]>("/api/aoi-sets", { params });
}

export function generateSlideAois(
  slideVersionId: string,
  input: {
    slideNumber?: number;
    merge?: boolean;
    replaceAuto?: boolean;
    resetAll?: boolean;
  } = {},
): Promise<AoiSet> {
  return apiFetch<AoiSet>(`/api/aoi-sets/slide/${slideVersionId}/generate`, {
    method: "POST",
    body: {
      slideNumber: input.slideNumber,
      merge: input.merge ?? false,
      replaceAuto: input.replaceAuto ?? false,
      resetAll: input.resetAll ?? false,
    },
    // Sinh AOI bằng AI có thể lâu hơn timeout mặc định 30s.
    timeoutMs: 120_000,
  });
}

export function saveSlideAois(
  slideVersionId: string,
  input: AoiSetSaveInput,
): Promise<AoiSet> {
  return apiFetch<AoiSet>(`/api/aoi-sets/slide/${slideVersionId}`, {
    method: "PUT",
    body: input,
  });
}

export function generateUiAois(
  uiSchemaVersion: string,
  components: AoiUiComponent[],
  merge = true,
): Promise<AoiSet> {
  return apiFetch<AoiSet>(`/api/aoi-sets/ui/${uiSchemaVersion}/generate`, {
    method: "POST",
    body: { components, merge },
    timeoutMs: 120_000,
  });
}

export function saveUiAois(
  uiSchemaVersion: string,
  input: AoiSetSaveInput,
): Promise<AoiSet> {
  return apiFetch<AoiSet>(`/api/aoi-sets/ui/${uiSchemaVersion}`, {
    method: "PUT",
    body: input,
  });
}

export function rebuildAoiHits(input: {
  courseId: string;
  lessonId?: string;
  fromTime?: string;
  toTime?: string;
  algorithmVersion?: string;
}): Promise<{ ok: boolean; runs: number; completed: number; failed: number }> {
  return apiFetch("/api/aoi/rebuild", {
    method: "POST",
    body: {
      courseId: input.courseId,
      lessonId: input.lessonId,
      fromTime: input.fromTime,
      toTime: input.toTime,
      algorithmVersion: input.algorithmVersion,
    },
    timeoutMs: 120_000,
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
