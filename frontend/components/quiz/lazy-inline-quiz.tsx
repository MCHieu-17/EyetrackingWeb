"use client";

import dynamic from "next/dynamic";
import { Skeleton } from "@/components/ui/skeleton";

const InlineQuizDynamic = dynamic(
  () => import("@/components/quiz/inline-quiz").then((mod) => mod.InlineQuiz),
  {
    ssr: false,
    loading: () => (
      <Skeleton className="h-full max-h-72 w-full rounded-2xl" />
    ),
  },
);

export function LazyInlineQuiz({
  quizId,
  onNext,
  hasNext,
}: {
  quizId: string;
  onNext?: () => void;
  hasNext?: boolean;
}) {
  return (
    <InlineQuizDynamic
      key={quizId}
      quizId={quizId}
      onNext={onNext}
      hasNext={hasNext}
    />
  );
}
