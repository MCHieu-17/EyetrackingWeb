"use client";

import { AssistantProvider } from "@/components/assistant/assistant-context";
import { ReaderContent } from "./reader-content";

export function LearningReader({ courseId }: { courseId: string }) {
  return (
    <AssistantProvider>
      <ReaderContent courseId={courseId} />
    </AssistantProvider>
  );
}
