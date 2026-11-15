"use client";

import { Icon } from "@/components/ui/icon";
import type { AoiEditorController } from "../use-aoi-editor";
import { AoiRow } from "./aoi-row";
import { GroupSection } from "./group-section";
import { NoLabelRow } from "./no-label-row";
import { KIND_ICON, KIND_LABEL, type AoiPanelModel } from "./panel-model";

export function SlideDefinitionList({
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
  if (controller.generatingSlide) {
    return (
      <div className="flex items-center gap-2 rounded-xl bg-[#f7f7f4] px-3 py-3 text-xs text-black/55">
        <Icon name="ri-loader-4-line" className="size-4 animate-spin" />
        Đang tìm vùng trên slide…
      </div>
    );
  }
  if (controller.generateSlideError) {
    return (
      <div className="rounded-xl border border-destructive/20 bg-destructive/5 px-3 py-3 text-xs text-destructive">
        <p>Không tạo được gợi ý vùng.</p>
        <button
          type="button"
          onClick={controller.retryGenerateSlide}
          className="mt-1 font-semibold underline"
        >
          Thử lại
        </button>
      </div>
    );
  }
  if (!model.slideRoot && model.slideLeaves.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-black/10 bg-[#f7f7f4] px-3 py-4 text-center text-xs leading-5 text-black/50">
        Chưa có vùng nào.
        <br />
        Kéo chuột trên slide để vẽ vùng đầu tiên.
      </div>
    );
  }

  const slideRoot = model.slideRoot;

  return (
    <>
      {slideRoot && (
        <div className="rounded-xl border border-black/10 bg-[#f7f7f4] px-2.5 py-2">
          <div className="flex items-center gap-2">
            <span className="size-2.5 shrink-0 rounded-full bg-black/25" />
            <Icon
              name="ri-slideshow-line"
              className="size-3.5 shrink-0 text-black/45"
            />
            <input
              value={slideRoot.name}
              onChange={(event) =>
                controller.renameAoi(slideRoot.code, event.target.value)
              }
              readOnly={!controller.canManage}
              aria-label="Tên slide"
              className="w-full truncate rounded-md border border-transparent bg-transparent px-1 py-0.5 text-xs font-semibold text-black outline-none hover:border-black/10 focus:border-black/20 focus:bg-white focus:ring-2 focus:ring-[#e8f1e6]"
            />
          </div>
          <p className="mt-0.5 pl-8 text-[10px] text-black/40">
            Toàn bộ trang — không xóa được
          </p>
        </div>
      )}

      {Object.entries(model.slideGroups).map(([kind, items]) => (
        <GroupSection
          key={kind}
          title={KIND_LABEL[kind] ?? kind}
          count={items.length}
          collapsed={!!collapsed[kind]}
          onToggle={() => onToggleSection(kind)}
        >
          {items.map((item) => (
            <AoiRow
              key={item.code}
              definition={item}
              selected={controller.selectedCode === item.code}
              hovered={hoveredCode === item.code}
              canManage={controller.canManage}
              subtitle={item.label ? `Nhãn: ${item.label}` : undefined}
              icon={KIND_ICON[item.kind ?? "custom"] ?? "ri-checkbox-blank-line"}
              onSelect={() => controller.setSelectedCode(item.code)}
              onHover={(value) => onHover(value ? item.code : null)}
              onRename={(name) => controller.renameAoi(item.code, name)}
              onDeactivate={() => controller.deactivateAoi(item.code)}
              onDelete={() => controller.deleteAoi(item.code)}
            />
          ))}
        </GroupSection>
      ))}

      <GroupSection
        title="Chưa đánh dấu"
        count={model.inactiveLeaves.length + 1}
        collapsed={!!collapsed.inactive}
        onToggle={() => onToggleSection("inactive")}
      >
        {model.inactiveLeaves.map((item) => (
          <AoiRow
            key={item.code}
            definition={item}
            selected={controller.selectedCode === item.code}
            hovered={hoveredCode === item.code}
            inactive
            canManage={controller.canManage}
            subtitle={item.label ? `Nhãn: ${item.label}` : undefined}
            icon={KIND_ICON[item.kind ?? "custom"] ?? "ri-checkbox-blank-line"}
            onSelect={() => controller.setSelectedCode(item.code)}
            onHover={(value) => onHover(value ? item.code : null)}
            onRename={(name) => controller.renameAoi(item.code, name)}
            onRestore={() => controller.restoreAoi(item.code)}
            onDelete={() => controller.deleteAoi(item.code)}
          />
        ))}
        <NoLabelRow />
      </GroupSection>
    </>
  );
}
