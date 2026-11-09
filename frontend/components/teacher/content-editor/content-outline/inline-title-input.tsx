"use client";

import { useState } from "react";
import { INPUT_CLS } from "@/components/teacher/workspace-ui";
import { cn } from "@/lib/utils";

/** Ô nhập tên dùng cho "Đổi tên chương" trong menu phụ. */
export function InlineTitleInput({
  value,
  ariaLabel,
  onCommit,
  onCancel,
}: {
  value: string;
  ariaLabel: string;
  onCommit: (value: string) => void;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState(value);
  return (
    <input
      autoFocus
      value={draft}
      onChange={(event) => setDraft(event.target.value)}
      onBlur={() => {
        if (draft.trim() && draft.trim() !== value) onCommit(draft.trim());
        else onCancel();
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter") event.currentTarget.blur();
        if (event.key === "Escape") {
          setDraft(value);
          onCancel();
        }
      }}
      aria-label={ariaLabel}
      className={cn(INPUT_CLS, "h-9 min-w-0 flex-1")}
    />
  );
}
