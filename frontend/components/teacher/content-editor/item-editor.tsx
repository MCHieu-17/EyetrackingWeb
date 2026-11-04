"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { EmptyState } from "@/components/ui/empty-state";
import { KIND_LABEL, QUIZ_STATUS_LABEL, QUIZ_STATUS_TONE } from "@/lib/content-labels";
import { cn } from "@/lib/utils";
import type { LessonNode } from "@/lib/types/domain";
import { LessonEditor } from "./lesson-editor";
import { LessonQuizEditor } from "./lesson-quiz-editor";

/**
 * Khung bên phải của tab Nội dung: soạn đúng MỘT mục đang chọn.
 *
 * Tên mục dùng chung một ô cho cả bài giảng và bài tập. Với bài tập, tên được
 * lưu qua PATCH assignment (backend đồng bộ luôn lesson.title) nên không còn
 * hai chỗ sửa cùng một dữ liệu.
 *
 * Cha truyền `key={lesson.id}` để state cục bộ tự nạp lại khi đổi mục.
 */
export function ItemEditor({
  lesson,
  moduleTitle,
  courseId,
  canManage,
  focusTitleToken,
  onRenameTitle,
  onChanged,
  onOpenOutline,
}: {
  lesson: LessonNode | null;
  moduleTitle: string | null;
  courseId: string;
  canManage: boolean;
  focusTitleToken: number;
  onRenameTitle: (lesson: LessonNode, title: string) => Promise<void>;
  onChanged: () => void;
  onOpenOutline: () => void;
}) {
  const titleRef = useRef<HTMLInputElement>(null);
  const [draftTitle, setDraftTitle] = useState(lesson?.title ?? "");
  const [savingTitle, setSavingTitle] = useState(false);
  const isQuiz = lesson?.kind === "quiz";

  // "Đổi tên" từ menu mục lục → đưa con trỏ vào ô tên chung.
  useEffect(() => {
    if (focusTitleToken === 0 || !titleRef.current) return;
    titleRef.current.focus();
    titleRef.current.select();
  }, [focusTitleToken]);

  const commitTitle = async () => {
    if (!lesson || !canManage) return;
    const clean = draftTitle.trim();
    if (!clean || clean === lesson.title) {
      setDraftTitle(lesson.title);
      return;
    }
    setDraftTitle(clean);
    setSavingTitle(true);
    try {
      await onRenameTitle(lesson, clean);
    } finally {
      setSavingTitle(false);
    }
  };

  if (!lesson) {
    return (
      <div className="space-y-3">
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="rounded-full border-black/10 bg-white lg:hidden"
          onClick={onOpenOutline}
        >
          <Icon name="ri-layout-left-line" className="size-4" />
          Mở mục lục
        </Button>
        <EmptyState
          icon="ri-layout-left-line"
          title="Chọn một mục để soạn"
          description="Mục lục liệt kê chương, bài giảng và bài tập. Chọn một mục để soạn nội dung ở đây."
        />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 lg:hidden">
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="rounded-full border-black/10 bg-white"
          onClick={onOpenOutline}
        >
          <Icon name="ri-layout-left-line" className="size-4" />
          Mục lục
        </Button>
      </div>

      <header className="rounded-[20px] border border-[#eeeee9] bg-white p-4 shadow-xs sm:p-5">
        <p className="flex flex-wrap items-center gap-1.5 text-xs font-medium text-black/60">
          <Icon name={isQuiz ? "ri-question-line" : "ri-book-open-line"} className="size-3.5" />
          <span className="rounded-full border border-black/10 bg-black/5 px-2 py-0.5 font-semibold text-black/75">
            {KIND_LABEL[lesson.kind] ?? "Nội dung"}
          </span>
          {isQuiz && lesson.quizStatus && (
            <span
              className={cn(
                "rounded-full border px-2 py-0.5 font-semibold",
                QUIZ_STATUS_TONE[lesson.quizStatus],
              )}
            >
              {QUIZ_STATUS_LABEL[lesson.quizStatus]}
            </span>
          )}
          {moduleTitle && <span className="truncate">· {moduleTitle}</span>}
        </p>

        <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <label className="min-w-0 flex-1">
            <span className="sr-only">{isQuiz ? "Tên bài tập" : "Tên bài giảng"}</span>
            <input
              ref={titleRef}
              value={draftTitle}
              onChange={(event) => setDraftTitle(event.target.value)}
              onBlur={() => void commitTitle()}
              onKeyDown={(event) => {
                if (event.key === "Enter") event.currentTarget.blur();
                if (event.key === "Escape") setDraftTitle(lesson.title);
              }}
              readOnly={!canManage}
              aria-label={isQuiz ? "Tên bài tập" : "Tên bài giảng"}
              className={cn(
                "w-full rounded-xl border border-transparent bg-transparent px-2 py-1 text-xl font-semibold tracking-[-0.02em] text-black transition-colors",
                canManage
                  ? "hover:border-black/10 focus-visible:border-black/20 focus-visible:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#e8f1e6]"
                  : "cursor-default",
              )}
            />
          </label>
          <span className="shrink-0 text-xs text-black/60">
            {!canManage
              ? "Bạn chỉ có quyền xem"
              : savingTitle
                ? "Đang lưu tên…"
                : "Sửa tên rồi nhấn Enter để lưu"}
          </span>
        </div>
      </header>

      {isQuiz ? (
        lesson.quizId ? (
          <LessonQuizEditor
            key={lesson.id}
            quizId={lesson.quizId}
            canManage={canManage}
            onChanged={onChanged}
          />
        ) : (
          <p className="rounded-[20px] border border-destructive/25 bg-destructive/5 p-4 text-sm text-destructive">
            Bài tập chưa sẵn sàng — hãy tải lại trang, hoặc xóa và tạo lại bài tập này.
          </p>
        )
      ) : (
        <LessonEditor key={lesson.id} lesson={lesson} courseId={courseId} canManage={canManage} />
      )}
    </div>
  );
}
