import type { AoiDefinitionInput } from "@/lib/api/aoi";
import { UI_COMPONENTS } from "@/lib/aoi/ui-components";

export const KIND_LABEL: Record<string, string> = {
  text: "TEXT",
  image: "IMAGE",
  table: "TABLE",
  drawing: "Hình vẽ",
  custom: "Tự chọn",
  ui: "Giao diện",
  system: "Hệ thống",
};

export const KIND_ICON: Record<string, string> = {
  text: "ri-text",
  image: "ri-image-line",
  table: "ri-table-line",
  drawing: "ri-shape-line",
  custom: "ri-checkbox-blank-line",
  ui: "ri-layout-masonry-line",
  system: "ri-slideshow-line",
};

type UiComponent = (typeof UI_COMPONENTS)[number];

export interface AoiPanelModel {
  slideRoot: AoiDefinitionInput | null;
  slideLeaves: AoiDefinitionInput[];
  activeLeaves: AoiDefinitionInput[];
  inactiveLeaves: AoiDefinitionInput[];
  slideGroups: Record<string, AoiDefinitionInput[]>;
  uiComponents: AoiDefinitionInput[];
  uiCustom: AoiDefinitionInput[];
  availableComponents: UiComponent[];
}

export interface AoiSelection {
  selectedInactive: boolean;
  selectedKind: string | null;
}

export function buildAoiPanelModel(
  slideDefinitions: AoiDefinitionInput[],
  uiDefinitions: AoiDefinitionInput[],
): AoiPanelModel {
  const slideRoot =
    slideDefinitions.find(
      (item) => item.isContainer && item.code.startsWith("slide_"),
    ) ?? null;
  const slideLeaves = slideDefinitions.filter((item) => !item.isContainer);
  const activeLeaves = slideLeaves.filter((item) => item.isActive !== false);
  const inactiveLeaves = slideLeaves.filter((item) => item.isActive === false);

  const slideGroups: Record<string, AoiDefinitionInput[]> = {};
  for (const item of slideDefinitions) {
    if (item.isContainer || item.isActive === false) continue;
    const key = item.kind ?? "custom";
    groupsAppend(slideGroups, key, item);
  }

  const uiComponents = uiDefinitions.filter((item) => item.kind === "ui");
  const uiCustom = uiDefinitions.filter((item) => item.kind === "custom");
  const availableComponents = UI_COMPONENTS.filter(
    (component) =>
      !uiDefinitions.some((item) => item.code === component.code),
  );

  return {
    slideRoot,
    slideLeaves,
    activeLeaves,
    inactiveLeaves,
    slideGroups,
    uiComponents,
    uiCustom,
    availableComponents,
  };
}

function groupsAppend(
  groups: Record<string, AoiDefinitionInput[]>,
  key: string,
  item: AoiDefinitionInput,
): void {
  const existing = groups[key];
  if (existing) existing.push(item);
  else groups[key] = [item];
}

export function resolveAoiSelection({
  tab,
  selectedCode,
  model,
}: {
  tab: "slide" | "ui";
  selectedCode: string | null;
  model: AoiPanelModel;
}): AoiSelection {
  if (!selectedCode) {
    return { selectedInactive: false, selectedKind: null };
  }

  if (tab === "slide") {
    const selectedInactive = model.inactiveLeaves.some(
      (item) => item.code === selectedCode,
    );
    const selectedKind = selectedInactive
      ? null
      : (model.activeLeaves.find((item) => item.code === selectedCode)?.kind ??
        null);
    return { selectedInactive, selectedKind };
  }

  const selectedKind =
    [...model.uiComponents, ...model.uiCustom].find(
      (item) => item.code === selectedCode,
    )?.kind ?? null;
  return { selectedInactive: false, selectedKind };
}

/**
 * Mở nhóm chứa vùng đang chọn. Trả lại cùng object khi không cần đổi để
 * tránh vòng setState trong lúc render.
 */
export function expandSelectedSections(
  collapsed: Record<string, boolean>,
  selection: AoiSelection,
): Record<string, boolean> {
  const keys: string[] = [];
  if (selection.selectedInactive && collapsed.inactive) {
    keys.push("inactive");
  }
  if (selection.selectedKind && collapsed[selection.selectedKind]) {
    keys.push(selection.selectedKind);
  }
  if (keys.length === 0) return collapsed;

  const next = { ...collapsed };
  for (const key of keys) next[key] = false;
  return next;
}
