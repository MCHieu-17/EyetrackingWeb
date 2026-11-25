"use client";

import { Alert } from "@/components/ui/alert";
import { Icon } from "@/components/ui/icon";
import { Input, Textarea } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { QUIZ_STATUS_LABEL, QUIZ_STATUS_TONE } from "@/lib/content-labels";
import { cn } from "@/lib/utils";
import type { QuizAssignmentStatus } from "@/lib/types/domain";

/** Thiết lập bài tập: trạng thái, làm lại, chatbot, thời lượng/hạn nộp/hướng dẫn. */
export function QuizSettings({
  assignmentId,
  assignmentTitle,
  status,
  message,
  allowRetry,
  allowChatbot,
  durationMinutes,
  dueAt,
  instructions,
  canManage,
  pending,
  onToggleAllowRetry,
  onToggleAllowChatbot,
  onDurationChange,
  onDueAtChange,
  onInstructionsChange,
}: {
  assignmentId: string;
  assignmentTitle: string;
  status: QuizAssignmentStatus;
  message: { tone: "ok" | "err"; text: string } | null;
  allowRetry: boolean;
  allowChatbot: boolean;
  durationMinutes: number;
  dueAt: string;
  instructions: string;
  canManage: boolean;
  pending: boolean;
  onToggleAllowRetry: (value: boolean) => void;
  onToggleAllowChatbot: (value: boolean) => void;
  onDurationChange: (value: number) => void;
  onDueAtChange: (value: string) => void;
  onInstructionsChange: (value: string) => void;
}) {
  return (
    <section className="space-y-3 rounded-2xl border border-border bg-card p-4 shadow-xs sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-base font-semibold text-foreground">Thiết lập bài tập</h3>
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
        <p className="flex items-start gap-2 rounded-xl border border-warning/30 bg-warning/8 px-3 py-2 text-xs leading-5 text-muted-foreground">
          <Icon name="ri-information-line" className="mt-0.5 size-3.5 shrink-0 text-warning" />
          Bài tập chưa được giao cho học viên. Bấm “Giao bài cho học viên” để xuất bản khóa học
          và đưa bài tập vào.
        </p>
      )}

      {message && (
        <Alert
          variant={message.tone === "ok" ? "success" : "destructive"}
          title={message.text}
        />
      )}

      <div className="flex flex-col gap-3 rounded-xl border border-border bg-accent/45 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <h4 className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <Icon name="ri-refresh-line" className="size-4 text-accent-foreground" />
            Cho phép học viên làm lại
          </h4>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">
            Bật để học viên được xoá kết quả cũ và làm lại từ đầu khi bài còn mở; đồng hồ làm bài
            chạy lại. Lưu ngay khi bật/tắt.
          </p>
        </div>
        <Switch
          checked={allowRetry}
          disabled={!canManage || pending}
          onCheckedChange={onToggleAllowRetry}
          ariaLabel={`Cho phép học viên làm lại — ${assignmentTitle}`}
        />
      </div>

      <div className="flex items-center justify-between gap-4 rounded-xl border border-border p-4">
        <div>
          <p className="text-sm font-semibold">Cho phép dùng chatbot khi làm bài</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Khi tắt, chatbot bị khóa trong toàn khóa học từ lúc bắt đầu đến khi nộp hoặc hết giờ. Lưu ngay khi bật/tắt.
          </p>
        </div>
        <Switch
          checked={allowChatbot}
          disabled={!canManage || pending}
          ariaLabel="Cho phép dùng chatbot khi làm bài"
          onCheckedChange={onToggleAllowChatbot}
        />
      </div>

      <details className="rounded-xl border border-border bg-muted/40 p-4">
        <summary className="cursor-pointer text-sm font-semibold text-foreground">
          Thời lượng, hạn nộp, hướng dẫn
          <span className="ml-2 text-xs font-normal text-muted-foreground">
            {durationMinutes} phút · {dueAt ? "có hạn nộp" : "không hạn nộp"}
          </span>
        </summary>
        <p className="mt-2 text-xs leading-5 text-muted-foreground">
          Các thay đổi trong mục này chỉ được áp dụng khi bấm “Lưu bài tập nháp” hoặc “Giao bài cho
          học viên”.
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <label
              htmlFor={`quiz-duration-${assignmentId}`}
              className="block text-sm font-medium text-foreground/75"
            >
              Thời lượng (phút) <span className="text-destructive">*</span>
            </label>
            <Input
              id={`quiz-duration-${assignmentId}`}
              type="number"
              min={1}
              max={1440}
              step={1}
              value={durationMinutes}
              readOnly={!canManage}
              onChange={(event) => onDurationChange(event.target.valueAsNumber || 1)}
              className="h-10"
            />
          </div>
          <div className="space-y-1.5">
            <label
              htmlFor={`quiz-due-${assignmentId}`}
              className="block text-sm font-medium text-foreground/75"
            >
              Hạn nộp (tùy chọn)
            </label>
            <Input
              id={`quiz-due-${assignmentId}`}
              type="datetime-local"
              value={dueAt}
              readOnly={!canManage}
              onChange={(event) => onDueAtChange(event.target.value)}
              className="h-10"
            />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <label
              htmlFor={`quiz-instructions-${assignmentId}`}
              className="block text-sm font-medium text-foreground/75"
            >
              Hướng dẫn làm bài
            </label>
            <Textarea
              id={`quiz-instructions-${assignmentId}`}
              value={instructions}
              readOnly={!canManage}
              onChange={(event) => onInstructionsChange(event.target.value)}
              placeholder="Nêu yêu cầu, quy tắc và điều học viên cần lưu ý…"
              className="min-h-16"
            />
          </div>
        </div>
      </details>
    </section>
  );
}
