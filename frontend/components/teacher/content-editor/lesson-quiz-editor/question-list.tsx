"use client";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import type { QuizQuestion } from "@/lib/types/domain";
import { QuestionPreview } from "./question-preview";

/** Danh sách câu hỏi bên trái: nút thêm và các dòng xem nhanh. */
export function QuestionList({
  questions,
  selectedIndex,
  canManage,
  onSelect,
  onAdd,
}: {
  questions: QuizQuestion[];
  selectedIndex: number;
  canManage: boolean;
  onSelect: (index: number) => void;
  onAdd: () => void;
}) {
  return (
    <div className="space-y-2">
      {canManage && (
        <Button
          type="button"
          className="w-full justify-center rounded-full"
          onClick={onAdd}
        >
          <Icon name="ri-add-line" className="size-4" />
          Thêm câu hỏi
        </Button>
      )}
      <ul className="space-y-1.5">
        {questions.map((question, index) => (
          <QuestionPreview
            key={question.id}
            question={question}
            index={index}
            active={index === selectedIndex}
            onSelect={() => onSelect(index)}
          />
        ))}
      </ul>
      {questions.length === 0 && (
        <p className="rounded-xl border border-dashed border-border bg-muted/40 px-3 py-4 text-center text-xs text-muted-foreground">
          Chưa có câu hỏi. Bấm “Thêm câu hỏi” để bắt đầu.
        </p>
      )}
    </div>
  );
}
