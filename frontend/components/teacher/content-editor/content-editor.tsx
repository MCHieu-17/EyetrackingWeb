"use client";

import { useCallback, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
import { ItemEditor } from "./item-editor";
import { PublishChecklistDialog, publishReport } from "./publish-checklist";

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
  const { changeStatus, saving: publishing } = useCourseStatus(courseId);
  const {
    data: tree = [],
    isFetching: treeFetching,
    isError: treeError,
    refetch: refetchTree,
  } = useCourseTree(courseId);

  const [selection, setSelection] = useState<string | null>(null);
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

  const errText = (e: unknown) => (e instanceof Error ? e.message : "Lỗi không xác định");

  const refreshTree = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["teacher", "courses"] });
    if (courseId) queryClient.invalidateQueries({ queryKey: ["teacher", "course-tree", courseId] });
  }, [queryClient, courseId]);

  // Mục đang mở: lựa chọn rõ ràng, hoặc mặc định mục đầu tiên (không cần effect).
  const firstItemId = tree[0]?.lessons[0]?.id ?? null;
  const activeId = selection ?? firstItemId;

  let selectedLesson: LessonNode | null = null;
  let selectedModule: ModuleNode | null = null;
  for (const mod of tree) {
    const lesson = mod.lessons.find((item) => item.id === activeId);
    if (lesson) {
      selectedLesson = lesson;
      selectedModule = mod;
      break;
    }
  }

  const totalLessons = tree.flatMap((m) => m.lessons).filter((l) => l.kind === "lesson").length;
  const totalQuizzes = tree.flatMap((m) => m.lessons).filter((l) => l.kind === "quiz").length;
  const totalSlides = tree.flatMap((m) => m.lessons).reduce((sum, l) => sum + l.slides, 0);
  const totalItems = totalLessons + totalQuizzes;

  const report = useMemo(() => publishReport(courseTitle, tree), [courseTitle, tree]);

  const openModuleOf = (lessonId: string) => {
    const owner = tree.find((module) => module.lessons.some((item) => item.id === lessonId));
    if (owner) setExpanded((prev) => ({ ...prev, [owner.id]: true }));
  };

  /** Chọn mục — có cảnh báo nếu trình soạn đang có thay đổi chưa lưu. */
  const selectItem = (lessonId: string, options?: { focusTitle?: boolean }) => {
    if (lessonId === activeId) {
      if (options?.focusTitle) setFocusTitleToken((token) => token + 1);
      return;
    }
    const proceed = () => {
      setSelection(lessonId);
      setOutlineOpen(false);
      openModuleOf(lessonId);
      if (options?.focusTitle) setFocusTitleToken((token) => token + 1);
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
    const key = ["teacher", "course-tree", courseId];
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
      courseId={courseId}
      canManage={canManage}
      selection={activeId}
      onSelect={(lessonId) => selectItem(lessonId)}
      expanded={expanded}
      onToggleModule={(moduleId) =>
        setExpanded((prev) => ({ ...prev, [moduleId]: !(prev[moduleId] ?? true) }))
      }
      onAddModule={() => void addModule()}
      onAddItem={addItem}
      onRenameLesson={(lesson) => selectItem(lesson.id, { focusTitle: true })}
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
      <div className="flex flex-col gap-4 border-b border-black/10 pb-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-black/45">
            Nội dung khóa học
          </p>
          <h2 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-black">
            Chương, bài giảng và bài tập
          </h2>
          <p className="mt-2 text-sm text-black/60">
            {tree.length} chương · {totalLessons} bài giảng · {totalQuizzes} bài tập · {totalSlides} trang
            {treeFetching && <span className="ml-2 text-black/45">· đang cập nhật…</span>}
          </p>
        </div>
        {canManage && (
          <div className="flex flex-wrap gap-2">
            {courseStatus === "published" ? (
              <span className="inline-flex h-9 items-center gap-1.5 rounded-full border border-[#cfe0ca] bg-[#e8f1e6] px-3.5 text-xs font-semibold text-[#3f573c]">
                <Icon name="ri-checkbox-circle-fill" className="size-4" />
                Đã xuất bản
              </span>
            ) : (
              <Button
                className="rounded-full"
                onClick={requestPublish}
                disabled={publishing || saving || reordering}
              >
                <Icon name="ri-rocket-2-line" className="size-4" />
                {publishing ? "Đang xuất bản…" : "Xuất bản"}
              </Button>
            )}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="outline"
                  className="rounded-full border-black/10 bg-white"
                  disabled={saving || reordering}
                >
                  <Icon name="ri-more-2-fill" className="size-4" />
                  Thao tác
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onSelect={() => setChecklistOpen(true)}>
                  <Icon name="ri-list-check-3" />
                  Kiểm tra nội dung
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => void addModule()} disabled={saving}>
                  <Icon name="ri-add-line" />
                  Thêm chương
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        )}
      </div>

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

            <div className="min-w-0">
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

      <ConfirmDialog
        open={confirmPublish}
        onOpenChange={setConfirmPublish}
        title="Xuất bản khóa học?"
        description="Sinh viên sẽ thấy khóa học trong danh sách và đăng ký được. Mọi bài giảng đã tải lên và bài tập đã giao hiện ngay với học viên."
        confirmLabel="Xuất bản"
        loading={publishing}
        onConfirm={async () => {
          setConfirmPublish(false);
          const ok = await changeStatus("published");
          if (ok) flash("ok", "Đã xuất bản khóa học.");
          else flash("err", "Không xuất bản được khóa học. Vui lòng thử lại.");
        }}
      />

      <ConfirmDialog
        open={moduleToDelete !== null}
        onOpenChange={(open) => !open && setModuleToDelete(null)}
        title={moduleToDelete ? `Xóa chương "${moduleToDelete.title}"?` : "Xóa chương?"}
        description={
          moduleToDelete && moduleToDelete.lessons.length > 0
            ? `Chương này còn ${moduleToDelete.lessons.length} mục — tất cả bài giảng, bài tập và slide bên trong cũng bị xóa.`
            : "Chương này sẽ bị xóa khỏi khóa học."
        }
        confirmLabel="Xóa chương"
        destructive
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

      <ConfirmDialog
        open={lessonToDelete !== null}
        onOpenChange={(open) => !open && setLessonToDelete(null)}
        title={
          lessonToDelete
            ? `Xóa ${lessonToDelete.kind === "quiz" ? "bài tập" : "bài giảng"} "${lessonToDelete.title}"?`
            : "Xóa mục?"
        }
        description={
          lessonToDelete?.kind === "quiz"
            ? "Bài tập, toàn bộ câu hỏi và kết quả làm bài của học viên sẽ bị xóa."
            : "Bài giảng, toàn bộ slide và dữ liệu điểm nhìn liên quan sẽ bị xóa."
        }
        confirmLabel="Xóa"
        destructive
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
