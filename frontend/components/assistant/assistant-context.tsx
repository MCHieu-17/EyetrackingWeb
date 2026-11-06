"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type AssistantMode = "reader" | "quiz" | "review";

export interface AssistantQuizContext {
  mode: "quiz" | "review";
  assignmentId: string;
  attemptId?: string | null;
  lessonId: string | null;
  draftAnswers?: Record<string, string[]>;
}

interface AssistantContextValue {
  mode: AssistantMode;
  assignmentId: string | null;
  attemptId: string | null;
  lessonId: string | null;
  draftAnswers?: Record<string, string[]>;
  setReaderMode: (mode: "reader" | "quiz") => void;
  setReaderLessonId: (lessonId: string | null) => void;
  setQuizContext: (context: AssistantQuizContext | null) => void;
}

const AssistantContext = createContext<AssistantContextValue | null>(null);

/**
 * Chia sẻ ngữ cảnh chat giữa reader và quiz.
 *
 * Chat panel chỉ được render một lần ở reader root. Khi InlineQuiz mount, nó
 * đăng ký mode/assignmentId/lessonId để panel chuyển từ "reader" sang "quiz"
 * hoặc "review" mà không cần render thêm widget chat thứ hai.
 */
export function AssistantProvider({ children }: { children: ReactNode }) {
  const [readerMode, setReaderModeState] = useState<"reader" | "quiz">("reader");
  const [readerLessonId, setReaderLessonIdState] = useState<string | null>(null);
  const [quizContext, setQuizContextState] = useState<AssistantQuizContext | null>(
    null,
  );

  const setReaderMode = useCallback((mode: "reader" | "quiz") => {
    setReaderModeState(mode);
  }, []);

  const setReaderLessonId = useCallback((lessonId: string | null) => {
    setReaderLessonIdState(lessonId);
  }, []);

  const setQuizContext = useCallback(
    (context: AssistantQuizContext | null) => {
      setQuizContextState(context);
    },
    [],
  );

  const value = useMemo<AssistantContextValue>(
    () => ({
      mode: quizContext?.mode ?? readerMode,
      assignmentId: quizContext?.assignmentId ?? null,
      attemptId: quizContext?.attemptId ?? null,
      draftAnswers: quizContext?.draftAnswers,
      lessonId: quizContext?.lessonId ?? readerLessonId,
      setReaderMode,
      setReaderLessonId,
      setQuizContext,
    }),
    [
      quizContext,
      readerMode,
      readerLessonId,
      setReaderMode,
      setReaderLessonId,
      setQuizContext,
    ],
  );

  return (
    <AssistantContext.Provider value={value}>{children}</AssistantContext.Provider>
  );
}

export function useAssistant(): AssistantContextValue {
  const context = useContext(AssistantContext);
  if (!context) {
    throw new Error("useAssistant must be used within AssistantProvider");
  }
  return context;
}
