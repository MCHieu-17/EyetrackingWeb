import type { ReactNode } from "react";
import { QUIZ_STATUS_LABEL } from "@/lib/content-labels";
import { cn } from "@/lib/utils";
import type { LessonNode } from "@/lib/types/domain";

type Tone = "ok" | "missing" | "draft" | "muted";

const TONE_CLS: Record<Tone, string> = {
  ok: "border-[#cfe0ca] bg-[#e8f1e6] text-[#3f573c]",
  missing: "border-destructive/25 bg-destructive/8 text-destructive",
  draft: "border-black/10 bg-black/5 text-black/60",
  muted: "border-black/10 bg-black/5 text-black/60",
};

/** Nhãn trạng thái nội dung: đủ/thiếu tài liệu, bản nháp, số câu… */
function StatusPill({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-semibold",
        TONE_CLS[tone],
      )}
    >
      {children}
    </span>
  );
}

export function itemStatus(lesson: LessonNode) {
  if (lesson.kind === "quiz") {
    const count = lesson.questionCount ?? 0;
    if (count === 0) return <StatusPill tone="missing">Chưa có câu hỏi</StatusPill>;
    if (lesson.quizStatus === "draft")
      return <StatusPill tone="draft">{QUIZ_STATUS_LABEL.draft} · {count} câu</StatusPill>;
    if (lesson.quizStatus === "closed")
      return <StatusPill tone="muted">{QUIZ_STATUS_LABEL.closed} · {count} câu</StatusPill>;
    return <StatusPill tone="ok">{QUIZ_STATUS_LABEL.published} · {count} câu</StatusPill>;
  }
  return lesson.slides > 0 ? (
    <StatusPill tone="ok">{lesson.slides} trang</StatusPill>
  ) : (
    <StatusPill tone="missing">Chưa có PDF</StatusPill>
  );
}
