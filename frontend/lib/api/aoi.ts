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
  label?: string | null;
  parentId: string | null;
  geometry: Record<string, unknown>;
  isContainer: boolean;
  kind: AoiKind;
  isActive: boolean;
}

export interface AoiCollection {
  id: string;
  scope: "slide" | "ui";
  slideId: string | null;
  uiSchema: string | null;
  definitions: AoiDefinition[];
}

export interface AoiDefinitionInput {
  code: string;
  name: string;
  label?: string | null;
  parentId?: string | null;
  geometry: Record<string, unknown>;
  isContainer?: boolean;
  kind?: AoiKind;
  isActive?: boolean;
}

interface AoiSaveInput {
  definitions: AoiDefinitionInput[];
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

export interface AoiLayoutSnapshot {
  id: string;
  presentationId: string;
  layoutGeneration: number;
  capturedAt: string;
}

interface ContentPresentation {
  id: string;
  sessionId: string;
  slideId: string | null;
  surface: "lesson" | "quiz";
  sequenceNo: number;
  startedAt: string;
}

export function fetchAois(params: {
  slideId?: string;
  uiSchema?: string;
} = {}): Promise<AoiCollection[]> {
  return apiFetch<AoiCollection[]>("/api/aois", { params });
}

export function saveSlideAois(
  slideId: string,
  input: AoiSaveInput,
): Promise<AoiCollection> {
  return apiFetch<AoiCollection>(`/api/aois/slides/${slideId}`, {
    method: "PUT",
    body: input,
  });
}

export function generateUiAois(
  uiSchema: string,
  components: AoiUiComponent[],
  merge = true,
): Promise<AoiCollection> {
  return apiFetch<AoiCollection>(`/api/aois/ui/${uiSchema}/generate`, {
    method: "POST",
    body: { components, merge },
    timeoutMs: 120_000,
  });
}

export function saveUiAois(
  uiSchema: string,
  input: AoiSaveInput,
): Promise<AoiCollection> {
  return apiFetch<AoiCollection>(`/api/aois/ui/${uiSchema}`, {
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
    slideId?: string | null;
    surface: "lesson" | "quiz";
    sequenceNo: number;
    /** UUID sinh mỗi lần vào slide; retry cùng UUID là idempotent. */
    clientPresentationId?: string;
    /** Thời điểm slide trở thành context hiện tại. */
    enteredAt?: string;
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
