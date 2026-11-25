"use client";

import { Icon } from "@/components/ui/icon";
import { friendlyUiName, uiIcon } from "@/lib/aoi/ui-components";
import type { AoiEditorController } from "../use-aoi-editor";
import { AoiRow } from "./aoi-row";
import { GroupSection } from "./group-section";
import { type AoiPanelModel } from "./panel-model";

export function UiDefinitionList({
  controller,
  model,
  collapsed,
  onToggleSection,
  hoveredCode,
  onHover,
}: {
  controller: AoiEditorController;
  model: AoiPanelModel;
  collapsed: Record<string, boolean>;
  onToggleSection: (key: string) => void;
  hoveredCode: string | null;
  onHover: (code: string | null) => void;
}) {
  if (controller.generatingUi) {
    return (
      <div className="flex items-center gap-2 rounded-xl bg-muted px-3 py-3 text-xs text-muted-foreground">
        <Icon name="ri-loader-4-line" className="size-4 animate-spin" />
        Đang tìm các phần của trang…
      </div>
    );
  }
  if (controller.generateUiError) {
    return (
      <div className="rounded-xl border border-destructive/20 bg-destructive/5 px-3 py-3 text-xs text-destructive">
        <p>Không tạo được danh sách phần.</p>
        <button
          type="button"
          onClick={controller.retryGenerateUi}
          className="mt-1 font-semibold underline"
        >
          Thử lại
        </button>
      </div>
    );
  }

  return (
    <>
      {model.uiComponents.length > 0 && (
        <GroupSection
          title="Đã chọn"
          count={model.uiComponents.length}
          collapsed={!!collapsed.ui}
          onToggle={() => onToggleSection("ui")}
        >
          {model.uiComponents.map((item) => (
            <AoiRow
              key={item.code}
              definition={item}
              selected={controller.selectedCode === item.code}
              hovered={hoveredCode === item.code}
              canManage={controller.canManage}
              icon={uiIcon(item.code)}
              onSelect={() => controller.setSelectedCode(item.code)}
              onHover={(value) => onHover(value ? item.code : null)}
              onRename={(name) => controller.renameAoi(item.code, name)}
              onDelete={() => controller.deleteAoi(item.code)}
            />
          ))}
        </GroupSection>
      )}

      {model.uiCustom.length > 0 && (
        <GroupSection
          title="Tự chọn"
          count={model.uiCustom.length}
          collapsed={!!collapsed.custom}
          onToggle={() => onToggleSection("custom")}
        >
          {model.uiCustom.map((item) => {
            const anchor =
              typeof item.geometry.anchor === "string"
                ? item.geometry.anchor
                : null;
            return (
              <AoiRow
                key={item.code}
                definition={item}
                selected={controller.selectedCode === item.code}
                hovered={hoveredCode === item.code}
                canManage={controller.canManage}
                icon="ri-checkbox-blank-line"
                subtitle={
                  anchor ? `Trong: ${friendlyUiName(anchor)}` : "Vùng tự vẽ"
                }
                onSelect={() => controller.setSelectedCode(item.code)}
                onHover={(value) => onHover(value ? item.code : null)}
                onRename={(name) => controller.renameAoi(item.code, name)}
                onDelete={() => controller.deleteAoi(item.code)}
              />
            );
          })}
        </GroupSection>
      )}

      {model.uiComponents.length === 0 && model.uiCustom.length === 0 && (
        <div className="rounded-xl border border-dashed border-border bg-muted px-3 py-4 text-center text-xs leading-5 text-muted-foreground">
          Bấm vào một phần của trang để chọn vùng.
        </div>
      )}

      {model.availableComponents.length > 0 && (
        <GroupSection
          title="Chưa chọn"
          count={model.availableComponents.length}
          collapsed={!!collapsed.available}
          onToggle={() => onToggleSection("available")}
        >
          {model.availableComponents.map((component) => (
            <button
              key={component.code}
              type="button"
              onClick={() => controller.createUiComponentAoi(component.code)}
              disabled={!controller.canManage}
              className="flex w-full items-center gap-2 rounded-xl border border-transparent px-2.5 py-2 text-left transition-colors hover:border-border hover:bg-muted disabled:opacity-50"
            >
              <Icon
                name={component.icon}
                className="size-3.5 shrink-0 text-muted-foreground"
              />
              <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
                {component.name}
              </span>
              <Icon name="ri-add-line" className="size-3.5 text-muted-foreground" />
            </button>
          ))}
        </GroupSection>
      )}
    </>
  );
}
