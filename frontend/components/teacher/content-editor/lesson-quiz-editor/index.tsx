"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ErrorState } from "@/components/ui/error-state";
import { Icon } from "@/components/ui/icon";
import { duplicateQuestion, newQuestion } from "@/components/quiz/quiz-question-editor";
import { useUnsavedGuard } from "@/components/teacher/unsaved-guard";
import { useQuizAssignment, useUpdateQuizAssignment } from "@/hooks/use-quiz";
import { draftPayload, isQuestionComplete, trimQuestion } from "@/lib/quiz-validation";
import type { QuizAssignmentStatus, QuizQuestion } from "@/lib/types/domain";
import {
  appendQuestion,
  insertQuestionAt,
  moveQuestionAt,
  quizFormFromAssignment,
  removeQuestionAt,
  serializeQuizForm,
  type QuizForm,
} from "../editor-helpers";
import { QuestionEditor } from "./question-editor";
import { QuestionList } from "./question-list";
import { QuizSettings } from "./quiz-settings";
import { SaveBar } from "./save-bar";

/**
 * Trình soạn bài tập trắc nghiệm: thiết lập bài + danh sách câu hỏi (trái) và
 * vùng sửa câu đang chọn (phải). Tên bài tập nằm ở header chung của ItemEditor.
 */
export function LessonQuizEditor({
  quizId,
  canManage,
  onChanged,
}: {
  quizId: string;
  canManage: boolean;
  onChanged: () => void;
}) {
  const { data: assignment, isLoading, isError, refetch } = useQuizAssignment(quizId);
  const updateAssignment = useUpdateQuizAssignment();
  const guard = useUnsavedGuard();

  const [hydratedId, setHydratedId] = useState<string | null>(null);
  const [instructions, setInstructions] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(30);
  const [dueAt, setDueAt] = useState("");
  const [status, setStatus] = useState<QuizAssignmentStatus>("draft");
  const [allowRetry, setAllowRetry] = useState(false);
  const [allowChatbot, setAllowChatbot] = useState(false);
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [baseline, setBaseline] = useState("");
  const [message, setMessage] = useState<{ tone: "ok" | "err"; text: string } | null>(null);
  const [saving, setSaving] = useState(false);

  // Render-phase hydrate một lần cho mỗi bài tập.
  if (assignment && hydratedId !== assignment.id) {
    const form = quizFormFromAssignment(assignment);
    setHydratedId(assignment.id);
    setInstructions(form.instructions);
    setDurationMinutes(form.durationMinutes);
    setDueAt(form.dueAt);
    setStatus(assignment.status);
    setAllowRetry(form.allowRetry);
    setAllowChatbot(form.allowChatbot);
    setQuestions(form.questions);
    setSelectedIndex(0);
    setBaseline(serializeQuizForm(form));
  }

  const form = useMemo<QuizForm>(
    () => ({ instructions, durationMinutes, dueAt, allowRetry, allowChatbot, questions }),
    [instructions, durationMinutes, dueAt, allowRetry, allowChatbot, questions],
  );
  const snapshot = useMemo(() => serializeQuizForm(form), [form]);
  const dirty = baseline !== "" && snapshot !== baseline;

  const incomplete = useMemo(
    () => questions.map((question, index) => ({ index, complete: isQuestionComplete(question) })),
    [questions],
  );
  const incompleteCount = incomplete.filter((entry) => !entry.complete).length;
  const totalPoints = questions.reduce((sum, question) => sum + (question.points || 0), 0);

  const flash = useCallback((tone: "ok" | "err", text: string) => {
    setMessage({ tone, text });
    if (tone === "ok") window.setTimeout(() => setMessage(null), 6000);
  }, []);

  const patchQuestion = (index: number, next: QuizQuestion) =>
    setQuestions((current) => current.map((item, i) => (i === index ? next : item)));

  const save = useCallback(
    async (target: QuizAssignmentStatus): Promise<boolean> => {
      if (!canManage) return false;

      if (target === "published") {
        if (questions.length === 0) {
          flash("err", "Cần ít nhất một câu hỏi trước khi giao bài.");
          return false;
        }
        if (incompleteCount > 0) {
          const firstBad = incomplete.find((entry) => !entry.complete);
          flash(
            "err",
            `Còn ${incompleteCount} câu chưa hoàn thiện. Sửa các câu được đánh dấu rồi giao bài.`,
          );
          if (firstBad) setSelectedIndex(firstBad.index);
          return false;
        }
      }

      const draft = draftPayload(questions);
      const payload = target === "published" ? questions.map(trimQuestion) : draft.questions;
      const dueIso = form.dueAt ? new Date(form.dueAt).toISOString() : null;

      setSaving(true);
      try {
        const saved = await updateAssignment.mutateAsync({
          id: quizId,
          patch: {
            instructions: form.instructions.trim(),
            durationMinutes: Math.max(1, form.durationMinutes || 1),
            dueAt: dueIso,
            status: target,
            allowRetry: form.allowRetry,
            allowChatbot: form.allowChatbot,
            // Schema PATCH từ chối mảng rỗng → chỉ gửi khi có câu hợp lệ.
            ...(payload.length ? { questions: payload } : {}),
          },
        });
        setStatus(saved.status);
        setBaseline(snapshot);
        onChanged();
        if (target === "published") {
          flash("ok", "Đã giao bài cho học viên.");
        } else if (draft.unsavedCount > 0) {
          flash(
            "ok",
            `Đã lưu bản nháp. ${draft.unsavedCount} câu chưa hoàn thiện vẫn giữ trên màn hình nhưng chưa lưu được lên hệ thống.`,
          );
        } else {
          flash("ok", "Đã lưu bản nháp.");
        }
        return true;
      } catch (error) {
        flash(
          "err",
          `Không lưu được bài tập: ${error instanceof Error ? error.message : "lỗi không xác định"}`,
        );
        return false;
      } finally {
        setSaving(false);
      }
    },
    [canManage, flash, form, incomplete, incompleteCount, onChanged, questions, quizId, snapshot, updateAssignment],
  );

  // Cảnh báo "còn thay đổi chưa lưu" khi giáo viên chuyển mục / chuyển tab / rời trang.
  // Câu dở không lưu được lên server → chặn "Lưu & tiếp tục" để không mất âm thầm.
  useEffect(() => {
    if (!guard || !canManage) return;
    return guard.register({
      label: "bài tập",
      isDirty: () => dirty,
      save: async () => {
        if (incompleteCount > 0) {
          flash(
            "err",
            `Còn ${incompleteCount} câu chưa hoàn thiện. Hoàn thiện hoặc bỏ các câu này trước khi rời đi.`,
          );
          return false;
        }
        return save("draft");
      },
    });
  }, [guard, canManage, dirty, incompleteCount, flash, save]);

  // Cho phép làm lại: bật/tắt là lưu ngay (không cần bấm Lưu nháp).
  const toggleAllowRetry = async (value: boolean) => {
    const previous = allowRetry;
    setAllowRetry(value);
    try {
      await updateAssignment.mutateAsync({ id: quizId, patch: { allowRetry: value } });
      setBaseline(serializeQuizForm({ ...form, allowRetry: value, questions }));
      onChanged();
      flash("ok", value ? "Đã cho phép học viên làm lại bài này." : "Đã tắt cho phép làm lại.");
    } catch {
      setAllowRetry(previous);
      flash("err", "Không đổi được thiết lập làm lại. Vui lòng thử lại.");
    }
  };

  const toggleAllowChatbot = async (value: boolean) => {
    try {
      await updateAssignment.mutateAsync({ id: quizId, patch: { allowChatbot: value } });
      setAllowChatbot(value);
      setBaseline((current) =>
        current
          ? serializeQuizForm({ ...(JSON.parse(current) as QuizForm), allowChatbot: value })
          : current,
      );
      onChanged();
      flash("ok", "Đã cập nhật quyền dùng chatbot.");
    } catch (error) {
      flash("err", `Không cập nhật được: ${error instanceof Error ? error.message : "lỗi kết nối"}`);
    }
  };

  const addQuestion = () => {
    const update = appendQuestion(questions, newQuestion());
    setQuestions(update.questions);
    setSelectedIndex(update.selectedIndex);
  };

  const removeQuestion = (index: number) => {
    const update = removeQuestionAt(questions, index);
    setQuestions(update.questions);
    setSelectedIndex(update.selectedIndex);
  };

  const moveQuestion = (index: number, direction: -1 | 1) => {
    const update = moveQuestionAt(questions, index, direction);
    setQuestions(update.questions);
    setSelectedIndex(update.selectedIndex);
  };

  const duplicateAt = (index: number) => {
    const update = insertQuestionAt(questions, index, duplicateQuestion(questions[index]));
    setQuestions(update.questions);
    setSelectedIndex(update.selectedIndex);
  };

  if (isLoading) {
    return <p className="text-sm text-black/55">Đang tải bài tập…</p>;
  }
  if (isError) {
    return (
      <ErrorState
        title="Không tải được bài tập"
        description="Vui lòng kiểm tra kết nối và thử lại."
        onRetry={() => void refetch()}
      />
    );
  }
  if (!assignment) {
    return <p className="text-sm text-destructive">Không tải được bài tập.</p>;
  }

  const selected = questions[selectedIndex] ?? null;

  return (
    <div className="space-y-5">
      <QuizSettings
        assignmentId={assignment.id}
        assignmentTitle={assignment.title}
        status={status}
        message={message}
        allowRetry={allowRetry}
        allowChatbot={allowChatbot}
        durationMinutes={durationMinutes}
        dueAt={dueAt}
        instructions={instructions}
        canManage={canManage}
        pending={updateAssignment.isPending}
        onToggleAllowRetry={(value) => void toggleAllowRetry(value)}
        onToggleAllowChatbot={(value) => void toggleAllowChatbot(value)}
        onDurationChange={setDurationMinutes}
        onDueAtChange={setDueAt}
        onInstructionsChange={setInstructions}
      />

      {/* Danh sách câu hỏi + vùng sửa câu đang chọn */}
      <section className="rounded-[20px] border border-[#eeeee9] bg-white p-4 shadow-xs sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-base font-semibold text-black">Câu hỏi</h3>
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-xs font-medium text-black/60">
              {questions.length} câu · {totalPoints} điểm
            </span>
            {incompleteCount > 0 && (
              <span className="flex items-center gap-1.5 text-xs font-semibold text-warning">
                <Icon name="ri-error-warning-line" className="size-3.5" />
                {incompleteCount} câu chưa hoàn thiện
              </span>
            )}
          </div>
        </div>

        <div className="mt-3 grid gap-4 lg:grid-cols-[minmax(0,270px)_minmax(0,1fr)] lg:items-start">
          <QuestionList
            questions={questions}
            selectedIndex={selectedIndex}
            canManage={canManage}
            onSelect={setSelectedIndex}
            onAdd={addQuestion}
          />

          <div>
            <QuestionEditor
              question={selected}
              index={selectedIndex}
              canRemove={canManage && questions.length > 1}
              canMoveUp={canManage && selectedIndex > 0}
              canMoveDown={canManage && selectedIndex < questions.length - 1}
              onChange={(next) => patchQuestion(selectedIndex, next)}
              onRemove={() => removeQuestion(selectedIndex)}
              onDuplicate={() => duplicateAt(selectedIndex)}
              onMoveUp={() => moveQuestion(selectedIndex, -1)}
              onMoveDown={() => moveQuestion(selectedIndex, 1)}
            />
          </div>
        </div>
      </section>

      {canManage && (
        <SaveBar
          dirty={dirty}
          status={status}
          questionCount={questions.length}
          incompleteCount={incompleteCount}
          saving={saving}
          onSaveDraft={() => void save("draft")}
          onSavePublished={() => void save("published")}
        />
      )}
    </div>
  );
}
