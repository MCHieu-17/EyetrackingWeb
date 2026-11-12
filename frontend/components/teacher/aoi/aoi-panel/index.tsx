"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Icon } from "@/components/ui/icon";
import { FullPageSpinner } from "@/components/ui/spinner";
import type { AoiDefinitionInput } from "@/lib/api/aoi";
import {
  UI_COMPONENTS,
  friendlyUiName,
  uiIcon,
} from "@/lib/aoi/ui-components";
import { cn } from "@/lib/utils";
import type { AoiEditorController } from "../use-aoi-editor";
import { AoiRow } from "./aoi-row";
import { GroupSection } from "./group-section";
import { HelpDialog } from "./help-dialog";
import { NoLabelRow } from "./no-label-row";

const KIND_LABEL: Record<string, string> = {
  text: "TEXT",
  image: "IMAGE",
  table: "TABLE",
  drawing: "Hình vẽ",
  custom: "Tự chọn",
  ui: "Giao diện",
  system: "Hệ thống",
};

const KIND_ICON: Record<string, string> = {
  text: "ri-text",
  image: "ri-image-line",
  table: "ri-table-line",
  drawing: "ri-shape-line",
  custom: "ri-checkbox-blank-line",
  ui: "ri-layout-masonry-line",
  system: "ri-slideshow-line",
};

export function AoiPanel({
  courseId,
  controller,
  hoveredCode,
  onHover,
  hiddenCodes,
  onToggleHidden,
}: {
  courseId: string;
  controller: AoiEditorController;
  hoveredCode: string | null;
  onHover: (code: string | null) => void;
  hiddenCodes: Set<string>;
  onToggleHidden: (code: string) => void;
}) {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [helpOpen, setHelpOpen] = useState(false);
  const [regenerateOpen, setRegenerateOpen] = useState(false);
  const [hint, setHint] = useState<string | null>(null);

  const showHint = (text: string) => {
    setHint(text);
    window.setTimeout(() => setHint(null), 4000);
  };

  const slideRoot = controller.slideDefinitions.find(
    (item) => item.isContainer && item.code.startsWith("slide_"),
  );
  const slideLeaves = controller.slideDefinitions.filter(
    (item) => !item.isContainer,
  );
  const activeLeaves = slideLeaves.filter((item) => item.isActive !== false);
  const inactiveLeaves = slideLeaves.filter((item) => item.isActive === false);
  const slideGroups = useMemo(() => {
    const groups: Record<string, AoiDefinitionInput[]> = {};
    for (const item of controller.slideDefinitions) {
      if (item.isContainer || item.isActive === false) continue;
      const key = item.kind ?? "custom";
      groups[key] = [...(groups[key] ?? []), item];
    }
    return groups;
  }, [controller.slideDefinitions]);

  const uiComponents = controller.uiDefinitions.filter(
    (item) => item.kind === "ui",
  );
  const uiCustom = controller.uiDefinitions.filter(
    (item) => item.kind === "custom",
  );
  const availableComponents = UI_COMPONENTS.filter(
    (component) =>
      !controller.uiDefinitions.some((item) => item.code === component.code),
  );

  const selectedInactive =
    controller.tab === "slide" &&
    inactiveLeaves.some((item) => item.code === controller.selectedCode);
  const selectedKind =
    controller.tab === "slide"
      ? selectedInactive
        ? undefined
        : activeLeaves.find((item) => item.code === controller.selectedCode)
            ?.kind
      : controller.uiDefinitions.find(
          (item) => item.code === controller.selectedCode,
        )?.kind;

  if (selectedInactive && collapsed.inactive) {
    setCollapsed((prev) => ({ ...prev, inactive: false }));
  }
  if (selectedKind && collapsed[selectedKind]) {
    setCollapsed((prev) => ({ ...prev, [selectedKind]: false }));
  }

  const save = controller.activeSave;
  const saveLabel =
    save.status === "saving"
      ? "Đang lưu…"
      : save.status === "error"
        ? "Không lưu được"
        : "Đã lưu";

  const renderSlideList = () => {
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
    if (!slideRoot && slideLeaves.length === 0) {
      return (
        <div className="rounded-xl border border-dashed border-black/10 bg-[#f7f7f4] px-3 py-4 text-center text-xs leading-5 text-black/50">
          Chưa có vùng nào.
          <br />
          Kéo chuột trên slide để vẽ vùng đầu tiên.
        </div>
      );
    }
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

        {Object.entries(slideGroups).map(([kind, items]) => (
          <GroupSection
            key={kind}
            title={KIND_LABEL[kind] ?? kind}
            count={items.length}
            collapsed={!!collapsed[kind]}
            onToggle={() =>
              setCollapsed((prev) => ({ ...prev, [kind]: !prev[kind] }))
            }
          >
            {items.map((item) => (
              <AoiRow
                key={item.code}
                definition={item}
                selected={controller.selectedCode === item.code}
                hovered={hoveredCode === item.code}
                hidden={hiddenCodes.has(item.code)}
                canManage={controller.canManage}
                icon={KIND_ICON[item.kind ?? "custom"] ?? "ri-checkbox-blank-line"}
                onSelect={() => controller.setSelectedCode(item.code)}
                onHover={(value) => onHover(value ? item.code : null)}
                onRename={(name) => controller.renameAoi(item.code, name)}
                onDeactivate={() => controller.deactivateAoi(item.code)}
                onToggleHidden={() => onToggleHidden(item.code)}
              />
            ))}
          </GroupSection>
        ))}

        <GroupSection
          title="Chưa đánh dấu"
          count={inactiveLeaves.length + 1}
          collapsed={!!collapsed.inactive}
          onToggle={() =>
            setCollapsed((prev) => ({ ...prev, inactive: !prev.inactive }))
          }
        >
          {inactiveLeaves.map((item) => (
            <AoiRow
              key={item.code}
              definition={item}
              selected={controller.selectedCode === item.code}
              hovered={hoveredCode === item.code}
              hidden={hiddenCodes.has(item.code)}
              inactive
              canManage={controller.canManage}
              icon={KIND_ICON[item.kind ?? "custom"] ?? "ri-checkbox-blank-line"}
              onSelect={() => controller.setSelectedCode(item.code)}
              onHover={(value) => onHover(value ? item.code : null)}
              onRename={(name) => controller.renameAoi(item.code, name)}
              onRestore={() => controller.restoreAoi(item.code)}
              onToggleHidden={() => onToggleHidden(item.code)}
            />
          ))}
          <NoLabelRow />
        </GroupSection>
      </>
    );
  };

  const renderUiList = () => {
    if (controller.generatingUi) {
      return (
        <div className="flex items-center gap-2 rounded-xl bg-[#f7f7f4] px-3 py-3 text-xs text-black/55">
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
        {uiComponents.length > 0 && (
          <GroupSection
            title="Đã chọn"
            count={uiComponents.length}
            collapsed={!!collapsed.ui}
            onToggle={() =>
              setCollapsed((prev) => ({ ...prev, ui: !prev.ui }))
            }
          >
            {uiComponents.map((item) => (
              <AoiRow
                key={item.code}
                definition={item}
                selected={controller.selectedCode === item.code}
                hovered={hoveredCode === item.code}
                hidden={hiddenCodes.has(item.code)}
                canManage={controller.canManage}
                icon={uiIcon(item.code)}
                onSelect={() => controller.setSelectedCode(item.code)}
                onHover={(value) => onHover(value ? item.code : null)}
                onRename={(name) => controller.renameAoi(item.code, name)}
                onDelete={() => controller.deleteAoi(item.code)}
                onToggleHidden={() => onToggleHidden(item.code)}
              />
            ))}
          </GroupSection>
        )}

        {uiCustom.length > 0 && (
          <GroupSection
            title="Tự chọn"
            count={uiCustom.length}
            collapsed={!!collapsed.custom}
            onToggle={() =>
              setCollapsed((prev) => ({ ...prev, custom: !prev.custom }))
            }
          >
            {uiCustom.map((item) => {
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
                  hidden={hiddenCodes.has(item.code)}
                  canManage={controller.canManage}
                  icon="ri-checkbox-blank-line"
                  subtitle={
                    anchor
                      ? `Trong: ${friendlyUiName(anchor)}`
                      : "Vùng tự vẽ"
                  }
                  onSelect={() => controller.setSelectedCode(item.code)}
                  onHover={(value) => onHover(value ? item.code : null)}
                  onRename={(name) => controller.renameAoi(item.code, name)}
                  onDelete={() => controller.deleteAoi(item.code)}
                  onToggleHidden={() => onToggleHidden(item.code)}
                />
              );
            })}
          </GroupSection>
        )}

        {uiComponents.length === 0 && uiCustom.length === 0 && (
          <div className="rounded-xl border border-dashed border-black/10 bg-[#f7f7f4] px-3 py-4 text-center text-xs leading-5 text-black/50">
            Bấm vào một phần của trang để chọn vùng.
          </div>
        )}

        {availableComponents.length > 0 && (
          <GroupSection
            title="Chưa chọn"
            count={availableComponents.length}
            collapsed={!!collapsed.available}
            onToggle={() =>
              setCollapsed((prev) => ({
                ...prev,
                available: !prev.available,
              }))
            }
          >
            {availableComponents.map((component) => (
              <button
                key={component.code}
                type="button"
                onClick={() => controller.createUiComponentAoi(component.code)}
                disabled={!controller.canManage}
                className="flex w-full items-center gap-2 rounded-xl border border-transparent px-2.5 py-2 text-left transition-colors hover:border-black/10 hover:bg-[#f7f7f4] disabled:opacity-50"
              >
                <Icon
                  name={component.icon}
                  className="size-3.5 shrink-0 text-black/40"
                />
                <span className="min-w-0 flex-1 truncate text-xs text-black/65">
                  {component.name}
                </span>
                <Icon name="ri-add-line" className="size-3.5 text-black/35" />
              </button>
            ))}
          </GroupSection>
        )}
      </>
    );
  };

  if (controller.treeLoading) {
    return <FullPageSpinner label="Đang tải vùng phân tích…" />;
  }

  if (controller.treeError) {
    return (
      <div className="rounded-[20px] border border-destructive/20 bg-destructive/5 p-4 text-sm text-destructive">
        <p>Không tải được khóa học.</p>
        <button
          type="button"
          onClick={() => void controller.refetchTree()}
          className="mt-2 font-semibold underline"
        >
          Thử lại
        </button>
      </div>
    );
  }

  if (controller.lessons.length === 0) {
    return (
      <div className="rounded-[20px] border border-[#eeeee9] bg-white p-5 text-center shadow-xs">
        <p className="text-sm font-semibold text-black">Chưa có bài giảng</p>
        <p className="mt-1 text-xs text-black/55">
          Thêm bài giảng và tải slide trước khi tạo vùng.
        </p>
        <Button asChild size="sm" className="mt-3 rounded-full">
          <Link href={`/teacher/courses/${courseId}?tab=content`}>
            Mở tab Nội dung
          </Link>
        </Button>
      </div>
    );
  }

  return (
    <aside className="flex min-h-0 w-[380px] shrink-0 flex-col gap-3">
      <div className="rounded-[20px] border border-[#eeeee9] bg-white p-4 shadow-xs">
        <div className="flex items-start gap-2">
          <label className="min-w-0 flex-1">
            <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-black/40">
              Bài giảng
            </span>
            <select
              value={controller.activeLessonId}
              onChange={(event) => controller.selectLesson(event.target.value)}
              className="mt-1 w-full rounded-xl border border-[#eeeee9] bg-[#fdfdfa] px-2.5 py-2 text-xs font-medium text-black outline-none focus:border-black/20 focus:ring-2 focus:ring-[#e8f1e6]"
            >
              {controller.tree.map((module) => (
                <optgroup key={module.id} label={module.title}>
                  {module.lessons.map((lesson) => (
                    <option key={lesson.id} value={lesson.id}>
                      {lesson.title}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </label>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            className="mt-4 rounded-full"
            onClick={() => setHelpOpen(true)}
            aria-label="Cách dùng"
            title="Cách dùng"
          >
            <Icon name="ri-question-line" className="size-4" />
          </Button>
        </div>

        <div className="mt-3">
          <div className="flex rounded-full border border-[#eeeee9] bg-[#f7f7f4] p-1">
            <button
              type="button"
              onClick={() => controller.changeVersion("draft")}
              className={cn(
                "flex-1 rounded-full px-3 py-1.5 text-xs font-semibold transition-colors",
                controller.version === "draft"
                  ? "bg-black text-white"
                  : "text-black/55 hover:text-black",
              )}
            >
              Bản nháp
            </button>
            <button
              type="button"
              onClick={() => controller.changeVersion("published")}
              disabled={!controller.hasPublished}
              className={cn(
                "flex-1 rounded-full px-3 py-1.5 text-xs font-semibold transition-colors disabled:opacity-40",
                controller.version === "published"
                  ? "bg-black text-white"
                  : "text-black/55 hover:text-black",
              )}
            >
              Bản xuất bản
            </button>
          </div>
          <p className="mt-1.5 text-[10px] leading-4 text-black/45">
            {controller.version === "published"
              ? "Sinh viên đang học bản này."
              : "Bản đang soạn, chưa áp dụng cho sinh viên."}
          </p>
        </div>

        {controller.activeIsQuiz ? (
          <p className="mt-3 rounded-full bg-muted px-3 py-1.5 text-center text-xs font-medium text-foreground">
            Bài tập
          </p>
        ) : controller.slides.length > 0 ? (
          <div className="mt-3 flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="icon-sm"
              className="rounded-full"
              onClick={controller.prevSlide}
              disabled={controller.currentSlideIndex === 0}
              aria-label="Trang trước"
            >
              <Icon name="ri-arrow-left-s-line" className="size-4" />
            </Button>
            <div className="min-w-0 flex-1">
              <p className="text-center text-[11px] font-medium tabular-nums text-black/60">
                Trang {controller.currentSlideIndex + 1}/
                {controller.slides.length}
              </p>
              <div className="mt-1 h-1 rounded-full bg-black/10">
                <div
                  className="h-full rounded-full bg-[#36533a] transition-[width]"
                  style={{
                    width: `${
                      ((controller.currentSlideIndex + 1) /
                        controller.slides.length) *
                      100
                    }%`,
                  }}
                />
              </div>
            </div>
            <Button
              type="button"
              variant="outline"
              size="icon-sm"
              className="rounded-full"
              onClick={controller.nextSlide}
              disabled={
                controller.currentSlideIndex >= controller.slides.length - 1
              }
              aria-label="Trang sau"
            >
              <Icon name="ri-arrow-right-s-line" className="size-4" />
            </Button>
          </div>
        ) : (
          <div className="mt-3 rounded-xl border border-dashed border-black/10 bg-[#f7f7f4] px-3 py-3 text-center text-xs text-black/50">
            Bài giảng này chưa có slide.
            <Link
              href={`/teacher/courses/${courseId}?tab=content`}
              className="mt-1 block font-semibold text-[#36533a] underline"
            >
              Mở tab Nội dung
            </Link>
          </div>
        )}

        <div className="mt-3 flex rounded-full border border-[#eeeee9] bg-[#f7f7f4] p-1">
          <button
            type="button"
            onClick={() => controller.changeTab("slide")}
            disabled={controller.activeIsQuiz}
            className={cn(
              "flex-1 rounded-full px-3 py-1.5 text-xs font-semibold transition-colors disabled:opacity-40",
              controller.tab === "slide"
                ? "bg-black text-white"
                : "text-black/55 hover:text-black",
            )}
          >
            Slide
          </button>
          <button
            type="button"
            onClick={() => controller.changeTab("ui")}
            className={cn(
              "flex-1 rounded-full px-3 py-1.5 text-xs font-semibold transition-colors",
              controller.tab === "ui"
                ? "bg-black text-white"
                : "text-black/55 hover:text-black",
            )}
          >
            Giao diện
          </button>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          {controller.tab === "slide" ? (
            <>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="rounded-full border-black/10 bg-white"
                disabled={!controller.canManage || controller.mode === "interact"}
                onClick={() => showHint("Kéo chuột trên slide để vẽ vùng.")}
              >
                <Icon name="ri-add-line" className="size-4" />
                Vẽ vùng
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="rounded-full border-black/10 bg-white"
                disabled={
                  !controller.canManage ||
                  controller.mode === "interact" ||
                  controller.generatingSlide
                }
                onClick={() => setRegenerateOpen(true)}
              >
                <Icon name="ri-refresh-line" className="size-4" />
                Tạo lại gợi ý
              </Button>
            </>
          ) : (
            <>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="rounded-full border-black/10 bg-white"
                disabled={!controller.canManage || controller.mode === "interact"}
                onClick={() =>
                  showHint("Bấm vào một phần của trang để chọn vùng.")
                }
              >
                <Icon name="ri-cursor-line" className="size-4" />
                Chọn phần
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="rounded-full border-black/10 bg-white"
                disabled={!controller.canManage || controller.mode === "interact"}
                onClick={() => showHint("Kéo chuột trên trang để vẽ vùng.")}
              >
                <Icon name="ri-add-line" className="size-4" />
                Vẽ vùng
              </Button>
            </>
          )}
        </div>

        {hint && (
          <p className="mt-2 rounded-lg bg-[#e8f1e6] px-2.5 py-1.5 text-[11px] text-[#36533a]">
            {hint}
          </p>
        )}

        <div className="mt-3 flex items-center gap-1.5 text-[11px]">
          {save.status === "saving" ? (
            <Icon name="ri-loader-4-line" className="size-3.5 animate-spin text-black/45" />
          ) : save.status === "error" ? (
            <Icon name="ri-error-warning-line" className="size-3.5 text-destructive" />
          ) : (
            <Icon name="ri-check-line" className="size-3.5 text-[#36533a]" />
          )}
          <span
            className={cn(
              save.status === "error" ? "text-destructive" : "text-black/50",
            )}
          >
            {saveLabel}
          </span>
          {save.status === "error" && (
            <button
              type="button"
              onClick={save.retry}
              className="font-semibold text-destructive underline"
            >
              Thử lại
            </button>
          )}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto rounded-[20px] border border-[#eeeee9] bg-white p-3 shadow-xs">
        {controller.tab === "slide" ? (
          renderSlideList()
        ) : (
          <>
            {renderUiList()}
            <NoLabelRow />
          </>
        )}
      </div>

      <HelpDialog open={helpOpen} onOpenChange={setHelpOpen} />

      <Dialog open={regenerateOpen} onOpenChange={setRegenerateOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Tạo lại gợi ý vùng?</DialogTitle>
            <DialogDescription>
              PyMuPDF sẽ dò lại layout và tạo các vùng TEXT/IMAGE/TABLE.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2 px-6 pb-2">
            <Button
              type="button"
              variant="outline"
              className="h-auto w-full justify-start whitespace-normal px-3 py-3 text-left"
              disabled={controller.generatingSlide}
              onClick={() => {
                setRegenerateOpen(false);
                controller.regenerateSlide("auto");
              }}
            >
              <Icon name="ri-refresh-line" className="size-4 shrink-0" />
              <span className="min-w-0">
                <span className="block text-sm font-semibold">
                  Chỉ thay vùng gợi ý
                </span>
                <span className="mt-0.5 block text-xs font-normal text-muted-foreground">
                  Giữ các vùng tự vẽ và tên slide hiện có.
                </span>
              </span>
            </Button>
            <Button
              type="button"
              variant="outline"
              className="h-auto w-full justify-start whitespace-normal border-destructive/30 px-3 py-3 text-left text-destructive hover:bg-destructive/5"
              disabled={controller.generatingSlide}
              onClick={() => {
                setRegenerateOpen(false);
                controller.regenerateSlide("all");
              }}
            >
              <Icon name="ri-delete-bin-line" className="size-4 shrink-0" />
              <span className="min-w-0">
                <span className="block text-sm font-semibold">
                  Đặt lại toàn bộ
                </span>
                <span className="mt-0.5 block text-xs font-normal text-muted-foreground">
                  Xoá cả vùng tự vẽ, chỉ giữ container slide và tạo lại các
                  vùng gợi ý.
                </span>
              </span>
            </Button>
          </div>
          <div className="flex justify-end border-t border-border p-4">
            <Button variant="ghost" onClick={() => setRegenerateOpen(false)}>
              Hủy
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </aside>
  );
}
