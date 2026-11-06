import { apiFetch } from "./client";

export interface AoiDefinition {
  id: string;
  code: string;
  name: string;
  description: string | null;
  scope: "viewport" | "slide";
  parentId: string | null;
  selector: string | null;
  lessonContentId: string | null;
  isActive: boolean;
  metadata: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

export interface AoiDefinitionInput {
  code: string;
  name: string;
  description?: string | null;
  scope?: "viewport" | "slide";
  parentId?: string | null;
  selector?: string | null;
  lessonContentId?: string | null;
  isActive?: boolean;
  metadata?: Record<string, unknown>;
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

export function fetchAoiDefinitions(includeInactive = false): Promise<AoiDefinition[]> {
  return apiFetch<AoiDefinition[]>("/api/aoi-definitions", {
    params: { include_inactive: includeInactive },
  });
}

export function createAoiDefinition(input: AoiDefinitionInput): Promise<AoiDefinition> {
  return apiFetch<AoiDefinition>("/api/aoi-definitions", {
    method: "POST",
    body: input,
  });
}

export function updateAoiDefinition(
  id: string,
  input: Partial<AoiDefinitionInput>,
): Promise<AoiDefinition> {
  return apiFetch<AoiDefinition>(`/api/aoi-definitions/${id}`, {
    method: "PATCH",
    body: input,
  });
}

export function deleteAoiDefinition(id: string): Promise<{ ok: boolean }> {
  return apiFetch(`/api/aoi-definitions/${id}`, { method: "DELETE" });
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

export function rebuildAoiHits(input: {
  sessionId?: string;
  lessonId?: string;
  courseId?: string;
  fromTime?: string;
  toTime?: string;
}): Promise<{ ok: boolean; inserted: number }> {
  return apiFetch("/api/aoi/rebuild", { method: "POST", body: input });
}
