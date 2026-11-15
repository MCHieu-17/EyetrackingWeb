"use client";

import { useCallback, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { Alert } from "@/components/ui/alert";
import { ErrorState } from "@/components/ui/error-state";
import { Icon } from "@/components/ui/icon";
import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { useUnsavedGuard } from "@/components/teacher/unsaved-guard";
import { useCourseStatus } from "@/hooks/use-course-status";
import { useCourseTree } from "@/hooks/use-teacher";
import { updateQuizAssignment } from "@/lib/api/quiz";
import {
  createLesson,
  createModule,
  createModuleQuizItem,
  deleteLesson,
  deleteModule,
  reorderModuleItems,
  updateLesson,
  updateModule,
} from "@/lib/api/teacher";
import { cn } from "@/lib/utils";
import type { CourseStatus, LessonNode, ModuleNode } from "@/lib/types/domain";
import { ContentOutline } from "./content-outline";
import { DeleteLessonDialog, DeleteModuleDialog } from "./delete-dialogs";
import {
  countTree,
  errText,
  findSelectedItem,
  firstItemId,
  moduleOfLesson,
} from "./editor-helpers";
import { EditorHeader } from "./editor-header";
import { ItemEditor } from "./item-editor";
import { PublishChecklistDialog, publishReport } from "./publish-checklist";
import { PublishConfirmDialog } from "./publish-confirm-dialog";
import { queryKeys } from "@/lib/query-keys";

/**
 * Tab "Nội dung": mục lục (trái) + trình soạn mục đang chọn (phải).
 *
 * Đây là nơi duy nhất để soạn nội dung khóa học — kể cả khóa vừa tạo. Tên
 * chương/bài lưu ngay khi rời ô, PDF tải ngay khi chọn, còn bài tập trắc nghiệm
 * lưu theo nút "Lưu bài tập nháp"/"Giao bài".
 */
export function ContentEditor({
  courseId,
  canManage,
  courseTitle = "",
  courseStatus,
}: {
  courseId: string;
  canManage: boolean;
  courseTitle?: string;
  courseStatus: CourseStatus;
}) {
  const queryClient = useQueryClient();
  const guard = useUnsavedGuard();
  const searchParams = useSearchParams();
  const { changeStatus, saving: publishing } = useCourseStatus(courseId);
  const {
    data: tree = [],
    isFetching: treeFetching,
    isError: treeError,
    refetch: refetchTree,
  } = useCourseTree(courseId);

  const [selection, setSelection] = useState<string | null>(
    () => searchParams.get("lesson"),
  );
  const [focusTitleToken, setFocusTitleToken] = useState(0);
  const [focusModuleId, setFocusModuleId] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [outlineOpen, setOutlineOpen] = useState(false);
  const [lessonToDelete, setLessonToDelete] = useState<LessonNode | null>(null);
  const [moduleToDelete, setModuleToDelete] = useState<ModuleNode | null>(null);
  const [checklistOpen, setChecklistOpen] = useState(false);
  const [confirmPublish, setConfirmPublish] = useState(false);
  const [saving, setSaving] = useState(false);
  const [reordering, setReordering] = useState(false);
  const [statusMsg, setStatusMsg] = useState<{ tone: "ok" | "err"; text: string } | null>(null);

  const flash = useCallback((tone: "ok" | "err", text: string) => {
    setStatusMsg({ tone, text });
    window.setTimeout(() => setStatusMsg(null), 6000);
  }, []);

  const refreshTree = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: queryKeys.teacher.coursesRoot });
    if (courseId) queryClient.invalidateQueries({ queryKey: queryKeys.teacher.courseTree(courseId) });
  }, [queryClient, courseId]);

  // Mục đang mở: lựa chọn rõ ràng, hoặc mặc định mục đầu tiên (không cần effect).
  const activeId = selection ?? firstItemId(tree);

  const selected = findSelectedItem(tree, activeId);
  const selectedLesson = selected?.lesson ?? null;
  const selectedModule = selected?.module ?? null;

  const { totalLessons, totalQuizzes, totalSlides, totalItems } = countTree(tree);

  const report = useMemo(() => publishReport(courseTitle, tree), [courseTitle, tree]);

  const openModuleOf = (lessonId: string) => {
    const owner = moduleOfLesson(tree, lessonId);
    if (owner) setExpanded((prev) => ({ ...prev, [owner.id]: true }));
  };

  /** Đưa khung soạn vào tầm nhìn — hữu ích khi mục lục đang cuộn sâu hoặc trên mobile. */
  const scrollEditorIntoView = () => {
    window.setTimeout(() => {
      const el = document.getElementById("item-editor");
      if (!el) return;
      const rect = el.getBoundingClientRect();
      // Chỉ cuộn khi phần đầu khung soạn bị khuất hoặc nằm ngoài màn hình,
      // tránh giật trang khi mọi thứ đã hiển thị sẵn.
      if (rect.top < 88 || rect.top > window.innerHeight - 120) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }, 0);
  };

  /** Chọn mục — có cảnh báo nếu trình soạn đang có thay đổi chưa lưu. */
  const selectItem = (lessonId: string) => {
    if (lessonId === activeId) {
      // Bấm lại mục đang mở: đóng mục lục (mobile) và đưa khung soạn vào tầm nhìn.
      setOutlineOpen(false);
      scrollEditorIntoView();
      return;
    }
    const proceed = () => {
      setSelection(lessonId);
      setOutlineOpen(false);
      openModuleOf(lessonId);
      scrollEditorIntoView();
    };
    if (guard) guard.confirmLeave(proceed);
    else proceed();
  };

  const addModule = async () => {
    setSaving(true);
    try {
      const created = await createModule(courseId, `Chương ${tree.length + 1}`);
      setExpanded((prev) => ({ ...prev, [created.id]: true }));
      setFocusModuleId(created.id);
      refreshTree();
      flash("ok", "Đã thêm chương. Nhập tên chương rồi nhấn Enter.");
    } catch (e) {
      flash("err", `Không thêm được chương: ${errText(e)}`);
    } finally {
      setSaving(false);
    }
  };

  const addLesson = async (moduleId: string) => {
    setSaving(true);
    try {
      const created = await createLesson(moduleId, "Bài giảng mới");
      setSelection(created.id);
      setExpanded((prev) => ({ ...prev, [moduleId]: true }));
      setFocusTitleToken((token) => token + 1);
      setOutlineOpen(false);
      refreshTree();
      flash("ok", "Đã thêm bài giảng — tải PDF lên để sinh viên học được.");
    } catch (e) {
      flash("err", `Không thêm được bài giảng: ${errText(e)}`);
    } finally {
      setSaving(false);
    }
  };

  const addQuiz = async (moduleId: string) => {
    setSaving(true);
    try {
      const created = await createModuleQuizItem(moduleId, { title: "Bài tập mới" });
      setSelection(created.id);
      setExpanded((prev) => ({ ...prev, [moduleId]: true }));
      setFocusTitleToken((token) => token + 1);
      setOutlineOpen(false);
      refreshTree();
      flash("ok", "Đã thêm bài tập — soạn câu hỏi ở khung bên phải.");
    } catch (e) {
      flash("err", `Không thêm được bài tập: ${errText(e)}`);
    } finally {
      setSaving(false);
    }
  };

  /**
   * Thêm mục mới làm đổi mục đang chọn → phải hỏi trước nếu trình soạn còn
   * thay đổi chưa lưu, tránh unmount làm mất câu hỏi đang soạn dở.
   */
  const addItem = (moduleId: string, kind: "lesson" | "quiz") => {
    const proceed = () => {
      if (kind === "lesson") void addLesson(moduleId);
      else void addQuiz(moduleId);
    };
    if (guard) guard.confirmLeave(proceed);
    else proceed();
  };

  // Kéo thả: gửi lại toàn bộ thứ tự item của chương (backend yêu cầu danh sách
  // đầy đủ). Cập nhật lạc quan trước để thao tác mượt, lỗi thì khôi phục.
  const persistOrder = async (module: ModuleNode, next: LessonNode[]) => {
    const key = queryKeys.teacher.courseTree(courseId);
    const previous = queryClient.getQueryData<ModuleNode[]>(key);
    queryClient.setQueryData<ModuleNode[]>(key, (modules) =>
      modules?.map((item) => (item.id === module.id ? { ...item, lessons: next } : item)),
    );
    setReordering(true);
    try {
      await reorderModuleItems(
        module.id,
        next.map((lesson) => ({ kind: lesson.kind, id: lesson.id })),
      );
      refreshTree();
    } catch (e) {
      if (previous) queryClient.setQueryData(key, previous);
      flash("err", `Không sắp xếp được: ${errText(e)}`);
    } finally {
      setReordering(false);
    }
  };

  const commitRenameModule = async (moduleId: string, title: string) => {
    const clean = title.trim();
    if (!clean) return;
    try {
      await updateModule(moduleId, clean);
      refreshTree();
      flash("ok", "Đã đổi tên chương.");
    } catch (e) {
      flash("err", `Không đổi tên được chương: ${errText(e)}`);
    }
  };

  const commitRenameItem = async (lesson: LessonNode, title: string) => {
    try {
      if (lesson.kind === "quiz" && lesson.quizId) {
        await updateQuizAssignment(lesson.quizId, { title });
      } else {
        await updateLesson(lesson.id, { title });
      }
      refreshTree();
      flash("ok", "Đã lưu tên mục.");
    } catch (e) {
      flash("err", `Không lưu được tên: ${errText(e)}`);
    }
  };

  /** Xuất bản từ tab Nội dung — hỏi trước nếu trình soạn còn thay đổi chưa lưu. */
  const requestPublish = () => {
    const proceed = () => {
      if (report.blocking) setChecklistOpen(true);
      else setConfirmPublish(true);
    };
    if (guard) guard.confirmLeave(proceed);
    else proceed();
  };

  const outline = (
    <ContentOutline
      tree={tree}
      canManage={canManage}
      selection={activeId}
      onSelect={(lessonId) => selectItem(lessonId)}
      expanded={expanded}
      onToggleModule={(moduleId) =>
        setExpanded((prev) => ({ ...prev, [moduleId]: !(prev[moduleId] ?? true) }))
      }
      onAddModule={() => void addModule()}
      onAddItem={addItem}
      onRenameLesson={(lesson, title) => void commitRenameItem(lesson, title)}
      onRenameModule={(moduleId, title) => void commitRenameModule(moduleId, title)}
      onDeleteLesson={setLessonToDelete}
      onDeleteModule={setModuleToDelete}
      onReorder={(module, next) => void persistOrder(module, next)}
      focusModuleId={focusModuleId}
      busy={saving || reordering}
    />
  );

  return (
    <div className="space-y-5">
      <EditorHeader
        moduleCount={tree.length}
        totalLessons={totalLessons}
        totalQuizzes={totalQuizzes}
        totalSlides={totalSlides}
        treeFetching={treeFetching}
        canManage={canManage}
        courseStatus={courseStatus}
        publishing={publishing}
        saving={saving}
        reordering={reordering}
        onPublish={requestPublish}
      />

      {statusMsg && (
        <Alert
          variant={statusMsg.tone === "ok" ? "success" : "destructive"}
          title={statusMsg.text}
        />
      )}

      {treeError ? (
        <ErrorState
          title="Không tải được nội dung khóa học"
          description="Vui lòng kiểm tra kết nối và thử lại."
          onRetry={() => void refetchTree()}
        />
      ) : (
        <>
          {totalItems > 0 && report.issues.length > 0 && (
            <button
              type="button"
              onClick={() => setChecklistOpen(true)}
              className={cn(
                "flex w-full items-center gap-2 rounded-[16px] border px-4 py-3 text-left text-sm transition",
                report.blocking
                  ? "border-destructive/25 bg-destructive/5 hover:bg-destructive/8"
                  : "border-warning/30 bg-warning/8 hover:bg-warning/12",
              )}
            >
              <Icon
                name={report.blocking ? "ri-error-warning-line" : "ri-information-line"}
                className={cn("size-4 shrink-0", report.blocking ? "text-destructive" : "text-warning")}
              />
              <span className="text-black">
                {report.issues.length} mục cần hoàn thiện trước khi xuất bản
                {report.blocking ? "" : " (chỉ là cảnh báo)"} — xem danh sách
              </span>
            </button>
          )}

          <div className="lg:grid lg:grid-cols-[21rem_minmax(0,1fr)] lg:items-start lg:gap-8">
            <div className="hidden lg:sticky lg:top-28 lg:block">{outline}</div>

            <div id="item-editor" className="min-w-0 scroll-mt-28">
              <ItemEditor
                key={selectedLesson?.id ?? "empty"}
                lesson={selectedLesson}
                moduleTitle={selectedModule?.title ?? null}
                courseId={courseId}
                canManage={canManage}
                focusTitleToken={focusTitleToken}
                onRenameTitle={commitRenameItem}
                onChanged={refreshTree}
                onOpenOutline={() => setOutlineOpen(true)}
              />
            </div>
          </div>

          <Sheet open={outlineOpen} onOpenChange={setOutlineOpen}>
            <SheetContent side="left" className="max-w-sm">
              <SheetHeader>
                <SheetTitle>Mục lục</SheetTitle>
                <SheetDescription>Chọn chương hoặc mục để soạn nội dung.</SheetDescription>
              </SheetHeader>
              <SheetBody>{outline}</SheetBody>
            </SheetContent>
          </Sheet>
        </>
      )}

      <PublishChecklistDialog
        open={checklistOpen}
        onOpenChange={setChecklistOpen}
        report={report}
        onOpenItem={(lessonId) => {
          setChecklistOpen(false);
          selectItem(lessonId);
        }}
      />

      <PublishConfirmDialog
        open={confirmPublish}
        onOpenChange={setConfirmPublish}
        loading={publishing}
        onConfirm={async () => {
          setConfirmPublish(false);
          const error = await changeStatus("published");
          if (!error) flash("ok", "Đã xuất bản khóa học.");
          else flash("err", error);
        }}
      />

      <DeleteModuleDialog
        module={moduleToDelete}
        onOpenChange={(open) => !open && setModuleToDelete(null)}
        onConfirm={async () => {
          if (!moduleToDelete) return;
          const target = moduleToDelete;
          setModuleToDelete(null);
          try {
            await deleteModule(target.id);
            setSelection(null);
            refreshTree();
            flash("ok", `Đã xóa chương "${target.title}".`);
          } catch (e) {
            flash("err", `Không xóa được chương: ${errText(e)}`);
          }
        }}
      />

      <DeleteLessonDialog
        lesson={lessonToDelete}
        onOpenChange={(open) => !open && setLessonToDelete(null)}
        onConfirm={async () => {
          if (!lessonToDelete) return;
          const target = lessonToDelete;
          setLessonToDelete(null);
          try {
            await deleteLesson(target.id);
            if (selection === target.id) setSelection(null);
            refreshTree();
            flash("ok", `Đã xóa "${target.title}".`);
          } catch (e) {
            flash("err", `Không xóa được mục: ${errText(e)}`);
          }
        }}
      />
    </div>
  );
}
