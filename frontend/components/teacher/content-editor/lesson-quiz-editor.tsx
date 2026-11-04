"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Icon } from "@/components/ui/icon";
import { Input, Textarea } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { QuizQuestionEditor, duplicateQuestion, newQuestion } from "@/components/quiz/quiz-question-editor";
import { useUnsavedGuard } from "@/components/teacher/unsaved-guard";
import { useQuizAssignment, useUpdateQuizAssignment } from "@/hooks/use-quiz";
import { QUIZ_STATUS_LABEL, QUIZ_STATUS_TONE } from "@/lib/content-labels";
import { draftPayload, isQuestionComplete, questionIssues, trimQuestion } from "@/lib/quiz-validation";
import { cn } from "@/lib/utils";
import type { QuizAssignmentStatus, QuizQuestion } from "@/lib/types/domain";

function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

interface QuizForm {
  instructions: string;
  durationMinutes: number;
  dueAt: string;
  allowRetry: boolean;
  allowChatbot: boolean;
  questions: QuizQuestion[];
}

const serialize = (form: QuizForm) => JSON.stringify(form);

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
    const form: QuizForm = {
      instructions: assignment.instructions,
      durationMinutes: assignment.durationMinutes,
      dueAt: toLocalInput(assignment.dueAt),
      allowRetry: Boolean(assignment.allowRetry),
      allowChatbot: Boolean(assignment.allowChatbot),
      questions: assignment.questions,
    };
    setHydratedId(assignment.id);
    setInstructions(form.instructions);
    setDurationMinutes(form.durationMinutes);
    setDueAt(form.dueAt);
    setStatus(assignment.status);
    setAllowRetry(form.allowRetry);
    setAllowChatbot(form.allowChatbot);
    setQuestions(form.questions);
    setSelectedIndex(0);
    setBaseline(serialize(form));
  }

  const form = useMemo<QuizForm>(
    () => ({ instructions, durationMinutes, dueAt, allowRetry, allowChatbot, questions }),
    [instructions, durationMinutes, dueAt, allowRetry, allowChatbot, questions],
  );
  const snapshot = useMemo(() => serialize(form), [form]);
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
      setBaseline(serialize({ ...form, allowRetry: value, questions }));
      onChanged();
      flash("ok", value ? "Đã cho phép học viên làm lại bài này." : "Đã tắt cho phép làm lại.");
    } catch {
      setAllowRetry(previous);
      flash("err", "Không đổi được thiết lập làm lại. Vui lòng thử lại.");
    }
  };

  const addQuestion = () => {
    const next = [...questions, newQuestion()];
    setQuestions(next);
    setSelectedIndex(next.length - 1);
  };

  const removeQuestion = (index: number) => {
    if (questions.length <= 1) return;
    const next = questions.filter((_, i) => i !== index);
    setQuestions(next);
    setSelectedIndex((selected) => Math.min(selected, next.length - 1));
  };

  const moveQuestion = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= questions.length) return;
    const next = [...questions];
    [next[index], next[target]] = [next[target], next[index]];
    setQuestions(next);
    setSelectedIndex(target);
  };

  const duplicateAt = (index: number) => {
    const copy = duplicateQuestion(questions[index]);
    const next = [...questions.slice(0, index + 1), copy, ...questions.slice(index + 1)];
    setQuestions(next);
    setSelectedIndex(index + 1);
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
      {/* Thiết lập bài tập — tên bài đã nằm ở header chung. */}
      <section className="space-y-3 rounded-[20px] border border-[#eeeee9] bg-white p-4 shadow-xs sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-base font-semibold text-black">Thiết lập bài tập</h3>
          <span
            className={cn(
              "rounded-full border px-2.5 py-1 text-[11px] font-semibold",
              QUIZ_STATUS_TONE[status],
            )}
          >
            {QUIZ_STATUS_LABEL[status]}
          </span>
        </div>

        {status === "draft" && (
          <p className="flex items-start gap-2 rounded-[14px] border border-warning/30 bg-warning/8 px-3 py-2 text-xs leading-5 text-black/75">
            <Icon name="ri-information-line" className="mt-0.5 size-3.5 shrink-0 text-warning" />
            Bài tập đang ở bản nháp nên học viên CHƯA thấy. Bấm “Giao bài cho học viên” để đưa vào
            khóa học.
          </p>
        )}

        {message && (
          <Alert
            variant={message.tone === "ok" ? "success" : "destructive"}
            title={message.text}
          />
        )}

        <div className="flex flex-col gap-3 rounded-[16px] border border-[#dfe9dc] bg-[#e8f1e6]/45 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <h4 className="flex items-center gap-2 text-sm font-semibold text-black">
              <Icon name="ri-refresh-line" className="size-4 text-[#52704f]" />
              Cho phép học viên làm lại
            </h4>
            <p className="mt-1 text-xs leading-5 text-black/65">
              Bật để học viên được xoá kết quả cũ và làm lại từ đầu khi bài còn mở; đồng hồ làm bài
              chạy lại. Lưu ngay khi bật/tắt.
            </p>
          </div>
          <Switch
            checked={allowRetry}
            disabled={!canManage || updateAssignment.isPending}
            onCheckedChange={(value) => void toggleAllowRetry(value)}
            ariaLabel={`Cho phép học viên làm lại — ${assignment.title}`}
          />
        </div>

        <div className="flex items-center justify-between gap-4 rounded-[16px] border border-border p-4">
          <div>
            <p className="text-sm font-semibold">Cho phép dùng chatbot khi làm bài</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Khi tắt, chatbot bị khóa trong toàn khóa học từ lúc bắt đầu đến khi nộp hoặc hết giờ. Lưu ngay khi bật/tắt.
            </p>
          </div>
          <Switch checked={allowChatbot} disabled={!canManage || updateAssignment.isPending}
            ariaLabel="Cho phép dùng chatbot khi làm bài"
            onCheckedChange={async (value) => {
              try {
                await updateAssignment.mutateAsync({ id: quizId, patch: { allowChatbot: value } });
                setAllowChatbot(value);
                setBaseline((current) => current ? serialize({ ...JSON.parse(current), allowChatbot: value }) : current);
                onChanged();
                flash("ok", "Đã cập nhật quyền dùng chatbot.");
              } catch (error) {
                flash("err", `Không cập nhật được: ${error instanceof Error ? error.message : "lỗi kết nối"}`);
              }
            }} />
        </div>

        <details className="rounded-[16px] border border-black/10 bg-[#fdfdfa] p-4">
          <summary className="cursor-pointer text-sm font-semibold text-black">
            Thời lượng, hạn nộp, hướng dẫn
            <span className="ml-2 text-xs font-normal text-black/55">
              {durationMinutes} phút · {dueAt ? "có hạn nộp" : "không hạn nộp"}
            </span>
          </summary>
          <p className="mt-2 text-xs leading-5 text-black/60">
            Các thay đổi trong mục này chỉ được áp dụng khi bấm “Lưu bài tập nháp” hoặc “Giao bài cho
            học viên”.
          </p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <label
                htmlFor={`quiz-duration-${assignment.id}`}
                className="block text-sm font-medium text-black/75"
              >
                Thời lượng (phút) <span className="text-destructive">*</span>
              </label>
              <Input
                id={`quiz-duration-${assignment.id}`}
                type="number"
                min={1}
                max={1440}
                step={1}
                value={durationMinutes}
                readOnly={!canManage}
                onChange={(event) => setDurationMinutes(event.target.valueAsNumber || 1)}
                className="h-10"
              />
            </div>
            <div className="space-y-1.5">
              <label
                htmlFor={`quiz-due-${assignment.id}`}
                className="block text-sm font-medium text-black/75"
              >
                Hạn nộp (tùy chọn)
              </label>
              <Input
                id={`quiz-due-${assignment.id}`}
                type="datetime-local"
                value={dueAt}
                readOnly={!canManage}
                onChange={(event) => setDueAt(event.target.value)}
                className="h-10"
              />
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <label
                htmlFor={`quiz-instructions-${assignment.id}`}
                className="block text-sm font-medium text-black/75"
              >
                Hướng dẫn làm bài
              </label>
              <Textarea
                id={`quiz-instructions-${assignment.id}`}
                value={instructions}
                readOnly={!canManage}
                onChange={(event) => setInstructions(event.target.value)}
                placeholder="Nêu yêu cầu, quy tắc và điều học viên cần lưu ý…"
                className="min-h-16"
              />
            </div>
          </div>
        </details>
      </section>

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
          <div className="space-y-2">
            {canManage && (
              <Button
                type="button"
                className="w-full justify-center rounded-full"
                onClick={addQuestion}
              >
                <Icon name="ri-add-line" className="size-4" />
                Thêm câu hỏi
              </Button>
            )}
            <ul className="space-y-1.5">
              {questions.map((question, index) => {
                const complete = isQuestionComplete(question);
                const active = index === selectedIndex;
                return (
                  <li key={question.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedIndex(index)}
                      aria-current={active ? "true" : undefined}
                      aria-label={`Câu hỏi ${index + 1}`}
                      className={cn(
                        "flex w-full items-center gap-2 rounded-[14px] border px-2.5 py-2 text-left transition",
                        active
                          ? "border-[#6f8f69] bg-[#e8f1e6]/60"
                          : "border-[#eeeee9] bg-[#fdfdfa] hover:border-black/15",
                      )}
                    >
                      <span
                        className={cn(
                          "flex size-6 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold tabular-nums",
                          active ? "bg-black text-white" : "bg-black/5 text-black/60",
                        )}
                      >
                        {index + 1}
                      </span>
                      <span
                        className={cn(
                          "min-w-0 flex-1 truncate text-xs",
                          question.prompt.trim() ? "text-black" : "italic text-black/45",
                        )}
                      >
                        {question.prompt.trim() || "Chưa có nội dung"}
                      </span>
                      {!complete && (
                        <span
                          className="size-2 shrink-0 rounded-full bg-warning"
                          title={questionIssues(question).join(" · ")}
                          aria-label={questionIssues(question).join(" · ")}
                        />
                      )}
                      <span className="shrink-0 text-[11px] font-medium text-black/50 tabular-nums">
                        {question.points}đ
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
            {questions.length === 0 && (
              <p className="rounded-[14px] border border-dashed border-black/10 bg-[#fdfdfa] px-3 py-4 text-center text-xs text-black/55">
                Chưa có câu hỏi. Bấm “Thêm câu hỏi” để bắt đầu.
              </p>
            )}
          </div>

          <div>
            {selected ? (
              <QuizQuestionEditor
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
            ) : (
              <p className="rounded-[18px] border border-dashed border-black/10 bg-[#fdfdfa] px-4 py-10 text-center text-sm text-black/55">
                Chọn một câu hỏi ở danh sách bên trái, hoặc bấm “Thêm câu hỏi”.
              </p>
            )}
          </div>
        </div>
      </section>

      {canManage && (
        <div className="sticky bottom-3 z-10 flex flex-col gap-2 rounded-[20px] border border-[#eeeee9] bg-white/95 p-3 shadow-[0_10px_30px_rgba(30,35,25,0.08)] backdrop-blur-xl sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1 px-1">
            <p className="text-xs text-black/60">
              {dirty
                ? "Chưa lưu: thay đổi sẽ mất nếu rời mục này."
                : "Mọi thay đổi đã được lưu."}
            </p>
            {status !== "published" && questions.length === 0 && (
              <p className="text-xs text-black/55">Thêm ít nhất một câu hỏi để giao bài.</p>
            )}
            {status !== "published" && questions.length > 0 && incompleteCount > 0 && (
              <p className="text-xs font-medium text-warning">
                Còn {incompleteCount} câu chưa hoàn thiện — hoàn thiện trước khi giao bài.
              </p>
            )}
          </div>
          <div className="flex flex-col-reverse gap-2 sm:flex-row">
            <Button
              type="button"
              variant="outline"
              className="rounded-full border-black/10 bg-white"
              disabled={saving}
              onClick={() => void save("draft")}
            >
              {saving ? "Đang lưu…" : "Lưu bài tập nháp"}
            </Button>
            <Button
              type="button"
              className="rounded-full"
              disabled={
                saving ||
                status === "published" ||
                questions.length === 0 ||
                incompleteCount > 0
              }
              onClick={() => void save("published")}
            >
              {status === "published" ? "Đã giao bài" : saving ? "Đang lưu…" : "Giao bài cho học viên"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
