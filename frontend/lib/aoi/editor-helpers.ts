import type {
  AoiDefinition,
  AoiDefinitionInput,
  AoiSet,
} from "@/lib/api/aoi";

export function pickLatest(sets: AoiSet[] | undefined): AoiSet | null {
  if (!sets?.length) return null;
  return (
    sets.find((item) => item.state === "draft") ??
    sets.find((item) => item.state === "published") ??
    null
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

export function countCustom(definitions: AoiDefinitionInput[]): number {
  return definitions.filter((item) => item.kind === "custom").length;
}
