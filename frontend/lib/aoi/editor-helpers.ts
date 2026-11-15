import type {
  AoiDefinition,
  AoiDefinitionInput,
  AoiCollection,
} from "@/lib/api/aoi";

export function firstAoiCollection(
  collections: AoiCollection[] | undefined,
): AoiCollection | null {
  return collections?.[0] ?? null;
}

/** Collection rỗng vẫn là object truthy — chỉ coi là có dữ liệu khi có AOI thật. */
export function hasStoredAois(
  collection: AoiCollection | null | undefined,
): boolean {
  return Boolean(
    collection?.definitions.some((item) => item.code !== "no_label"),
  );
}

export function toInputs(definitions: AoiDefinition[]): AoiDefinitionInput[] {
  const codeById = new Map(
    definitions.map((item) => [item.id, item.code] as const),
  );
  return definitions
    .filter((item) => item.code !== "no_label")
    .map((item) => ({
      code: item.code,
      name: item.name,
      ...(item.label ? { label: item.label } : {}),
      parentId: item.parentId
        ? (codeById.get(item.parentId) ?? item.parentId)
        : null,
      geometry: item.geometry,
      isContainer: item.isContainer,
      kind: item.kind,
      isActive: item.isActive,
    }));
}

export function nextCustomCode(
  definitions: AoiDefinitionInput[],
  rootCode: string,
): string {
  let index = 1;
  while (definitions.some((item) => item.code === `${rootCode}_custom_${index}`)) {
    index += 1;
  }
  return `${rootCode}_custom_${index}`;
}

export function nextUiCustomCode(definitions: AoiDefinitionInput[]): string {
  let index = 1;
  while (definitions.some((item) => item.code === `ui_custom_${index}`)) {
    index += 1;
  }
  return `ui_custom_${index}`;
}

/** Nhãn slide kế tiếp: AOI_<max+1>. */
export function nextSlideLabel(definitions: AoiDefinitionInput[]): string {
  const numbers = definitions
    .map((item) => /^AOI_(\d+)$/.exec(item.label ?? ""))
    .filter((match): match is RegExpExecArray => match !== null)
    .map((match) => Number(match[1]));
  return `AOI_${Math.max(0, ...numbers) + 1}`;
}

/** Mã của vùng và toàn bộ vùng con (dùng khi xóa). */
export function collectAoiCodes(
  definitions: AoiDefinitionInput[],
  code: string,
): Set<string> {
  const targets = new Set([code]);
  let changed = true;
  while (changed) {
    changed = false;
    for (const item of definitions) {
      if (
        item.parentId &&
        targets.has(item.parentId) &&
        !targets.has(item.code)
      ) {
        targets.add(item.code);
        changed = true;
      }
    }
  }
  return targets;
}

export function countCustom(definitions: AoiDefinitionInput[]): number {
  return definitions.filter((item) => item.kind === "custom").length;
}
