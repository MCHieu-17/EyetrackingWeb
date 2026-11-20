import { STABLE_UI_ANCHORS } from "@/lib/aoi/ui-components";

export interface AoiRect {
  xMin: number;
  yMin: number;
  xMax: number;
  yMax: number;
}

export interface Box {
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface Draft {
  startX: number;
  startY: number;
  currentX: number;
  currentY: number;
}

export function numberValue(
  geometry: Record<string, unknown>,
  key: string,
): number {
  const value = Number(geometry[key]);
  return Number.isFinite(value) ? value : 0;
}

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}

export function normalizeRect(
  startX: number,
  startY: number,
  endX: number,
  endY: number,
): AoiRect {
  return {
    xMin: clamp01(Math.min(startX, endX)),
    yMin: clamp01(Math.min(startY, endY)),
    xMax: clamp01(Math.max(startX, endX)),
    yMax: clamp01(Math.max(startY, endY)),
  };
}

export function screenBox(
  startX: number,
  startY: number,
  endX: number,
  endY: number,
): Box {
  return {
    left: Math.min(startX, endX),
    top: Math.min(startY, endY),
    width: Math.abs(endX - startX),
    height: Math.abs(endY - startY),
  };
}

export function measureElements(
  shell: HTMLElement,
  container: HTMLElement,
): Map<string, DOMRect[]> {
  const containerRect = container.getBoundingClientRect();
  const map = new Map<string, DOMRect[]>();
  shell.querySelectorAll<HTMLElement>("[data-aoi]").forEach((element) => {
    const code = element.dataset.aoi?.trim();
    if (!code) return;
    const rect = element.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;
    const local = new DOMRect(
      rect.left - containerRect.left,
      rect.top - containerRect.top,
      rect.width,
      rect.height,
    );
    const list = map.get(code) ?? [];
    list.push(local);
    map.set(code, list);
  });
  return map;
}

export function measureSlide(
  shell: HTMLElement,
  container: HTMLElement,
): DOMRect | null {
  const canvas = shell.querySelector<HTMLCanvasElement>(
    '[data-aoi="slide"] canvas',
  );
  if (!canvas) return null;
  const rect = canvas.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) return null;
  const containerRect = container.getBoundingClientRect();
  return new DOMRect(
    rect.left - containerRect.left,
    rect.top - containerRect.top,
    rect.width,
    rect.height,
  );
}

export function findAnchor(
  box: Box,
  elements: Map<string, DOMRect[]>,
): { code: string; rect: DOMRect } | null {
  const candidates: { code: string; rect: DOMRect; area: number }[] = [];
  for (const [code, rects] of elements) {
    if (!STABLE_UI_ANCHORS.has(code)) continue;
    for (const rect of rects) {
      if (rect.width <= 0 || rect.height <= 0) continue;
      const contains =
        box.left >= rect.left - 1 &&
        box.top >= rect.top - 1 &&
        box.left + box.width <= rect.right + 1 &&
        box.top + box.height <= rect.bottom + 1;
      if (contains) {
        candidates.push({ code, rect, area: rect.width * rect.height });
      }
    }
  }
  if (candidates.length === 0) {
    const root = elements.get("reader-root")?.[0];
    return root ? { code: "reader-root", rect: root } : null;
  }
  candidates.sort((a, b) => a.area - b.area);
  const chosen = candidates[0];
  if ((elements.get(chosen.code)?.length ?? 0) > 1) {
    const unique = candidates.find(
      (candidate) => (elements.get(candidate.code)?.length ?? 0) === 1,
    );
    if (unique) return { code: unique.code, rect: unique.rect };
  }
  return { code: chosen.code, rect: chosen.rect };
}

export function relativeRect(box: Box, anchor: DOMRect): AoiRect {
  return {
    xMin: clamp01((box.left - anchor.left) / anchor.width),
    yMin: clamp01((box.top - anchor.top) / anchor.height),
    xMax: clamp01((box.left + box.width - anchor.left) / anchor.width),
    yMax: clamp01((box.top + box.height - anchor.top) / anchor.height),
  };
}
