"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { FullPageSpinner } from "@/components/ui/spinner";
import type { AoiEditorController } from "../use-aoi-editor";
import { HelpDialog } from "./help-dialog";
import { LessonSlideSelector } from "./lesson-slide-selector";
import { NoLabelRow } from "./no-label-row";
import { PanelActions } from "./panel-actions";
import { buildAoiPanelModel } from "./panel-model";
import { RegenerateDialog } from "./regenerate-dialog";
import { SlideDefinitionList } from "./slide-definition-list";
import { UiDefinitionList } from "./ui-definition-list";
import { useAoiPanelSections } from "./use-aoi-panel-sections";

export function AoiPanel({
  courseId,
  controller,
  hoveredCode,
  onHover,
}: {
  courseId: string;
  controller: AoiEditorController;
  hoveredCode: string | null;
  onHover: (code: string | null) => void;
}) {
  const [helpOpen, setHelpOpen] = useState(false);
  const [regenerateOpen, setRegenerateOpen] = useState(false);
  const [hint, setHint] = useState<string | null>(null);

  const showHint = (text: string) => {
    setHint(text);
    window.setTimeout(() => setHint(null), 4000);
  };

  const model = useMemo(
    () =>
      buildAoiPanelModel(
        controller.slideDefinitions,
        controller.uiDefinitions,
      ),
    [controller.slideDefinitions, controller.uiDefinitions],
  );
  const { collapsed, toggleSection } = useAoiPanelSections({
    tab: controller.tab,
    selectedCode: controller.selectedCode,
    model,
  });

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
        <LessonSlideSelector
          courseId={courseId}
          controller={controller}
          onHelpOpen={() => setHelpOpen(true)}
        />
        <PanelActions
          controller={controller}
          hint={hint}
          onShowHint={showHint}
          onOpenRegenerate={() => setRegenerateOpen(true)}
        />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto rounded-[20px] border border-[#eeeee9] bg-white p-3 shadow-xs">
        {controller.tab === "slide" ? (
          <SlideDefinitionList
            controller={controller}
            model={model}
            collapsed={collapsed}
            onToggleSection={toggleSection}
            hoveredCode={hoveredCode}
            onHover={onHover}
          />
        ) : (
          <>
            <UiDefinitionList
              controller={controller}
              model={model}
              collapsed={collapsed}
              onToggleSection={toggleSection}
              hoveredCode={hoveredCode}
              onHover={onHover}
            />
            <NoLabelRow />
          </>
        )}
      </div>

      <HelpDialog open={helpOpen} onOpenChange={setHelpOpen} />

      <RegenerateDialog
        controller={controller}
        open={regenerateOpen}
        onOpenChange={setRegenerateOpen}
      />
    </aside>
  );
}
