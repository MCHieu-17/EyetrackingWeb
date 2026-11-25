"use client";

import type { RefObject } from "react";
import { LazyInlineQuiz } from "@/components/quiz/lazy-inline-quiz";
import { ReaderFrame } from "@/components/reader/reader-frame";
import { LazyStudyAssistantChat } from "@/components/assistant/lazy-study-assistant-chat";
import { DisplayGuardOverlay } from "@/components/display-guard/display-guard-overlay";
import type { DisplayGuardState } from "@/hooks/use-display-guard";
import type { ChatCitation } from "@/lib/api/chat";
import type { LessonItem, ModuleItem, Slide } from "@/lib/types/domain";
import { ReaderBanners } from "./reader-banners";
import { ReaderSlideContent } from "./reader-slide-content";
import { CameraPreview } from "./camera-preview";
import { isGazeDotVisible, type GazeDotPosition } from "./reader-helpers";

type GazeSource = "real" | "simulated" | "off";

export interface ReaderViewProps {
  courseId: string;
  courseTitle: string;
  modules: ModuleItem[];
  activeLessonId: string;
  activeLesson: LessonItem | null;
  activeModule: ModuleItem | null;
  slides: Slide[];
  currentSlide: number;
  activeIsQuiz: boolean;
  quizId: string;
  /** Bài kế tiếp trong outline, dùng cho nút "Bài tiếp theo" của quiz. */
  nextLesson: LessonItem | undefined;
  slidesLoading: boolean;
  slidePdfUrl: string | null;
  currentContent: Slide | undefined;
  chatOpen: boolean;
  chatAllowed: boolean;
  chatReason: string | null;
  chatButtonRef: RefObject<HTMLButtonElement | null>;
  onToggleChat: () => void;
  onCloseChat: () => void;
  onSelectLesson: (lessonId: string) => void;
  onPrevSlide: () => void;
  onNextSlide: () => void;
  onCitationNavigate: (citation: ChatCitation) => boolean;
  gazeSource: GazeSource;
  calibrationRequired: boolean;
  /** Luồng camera dùng chung với gaze tracker (null = không có camera). */
  cameraPreviewStream: MediaStream | null;
  /** Cờ cấp khóa: giáo viên bật khung xem trước camera. */
  showCameraPreview: boolean;
  showGazeDot: boolean;
  gazeDot: GazeDotPosition | null;
  displayGuard: DisplayGuardState;
}

/**
 * Toàn bộ cây JSX của trình đọc. Không giữ state hay effect — mọi hành vi
 * (phiên học, gaze, presentation, điều hướng) do `ReaderContent` điều phối.
 */
export function ReaderView({
  courseId,
  courseTitle,
  modules,
  activeLessonId,
  activeLesson,
  activeModule,
  slides,
  currentSlide,
  activeIsQuiz,
  quizId,
  nextLesson,
  slidesLoading,
  slidePdfUrl,
  currentContent,
  chatOpen,
  chatAllowed,
  chatReason,
  chatButtonRef,
  onToggleChat,
  onCloseChat,
  onSelectLesson,
  onPrevSlide,
  onNextSlide,
  onCitationNavigate,
  gazeSource,
  calibrationRequired,
  cameraPreviewStream,
  showCameraPreview,
  showGazeDot,
  gazeDot,
  displayGuard,
}: ReaderViewProps) {
  const quizContent = quizId ? (
    <LazyInlineQuiz
      quizId={quizId}
      onNext={nextLesson ? () => onSelectLesson(nextLesson.id) : undefined}
      hasNext={Boolean(nextLesson)}
    />
  ) : (
    <p className="p-8 text-center text-sm text-muted-foreground">
      Bài tập chưa sẵn sàng.
    </p>
  );

  return (
    <>
      <ReaderFrame
        courseTitle={courseTitle}
        modules={modules}
        activeLessonId={activeLessonId}
        activeLesson={activeLesson}
        activeModule={activeModule}
        slides={slides}
        currentSlide={currentSlide}
        activeIsQuiz={activeIsQuiz}
        chatOpen={chatOpen}
        chatAllowed={chatAllowed}
        chatButtonRef={chatButtonRef}
        chatReason={chatReason}
        onToggleChat={onToggleChat}
        onSelectLesson={onSelectLesson}
        onPrevSlide={onPrevSlide}
        onNextSlide={onNextSlide}
        gazeSource={gazeSource}
        calibrationRequired={calibrationRequired}
        banners={
          <ReaderBanners
            courseId={courseId}
            activeLessonId={activeLessonId}
            calibrationRequired={calibrationRequired}
            gazeSource={gazeSource}
            hasContent={slides.length > 0 || activeIsQuiz}
          />
        }
        slideContent={
          <ReaderSlideContent
            slidesLoading={slidesLoading}
            slidePdfUrl={slidePdfUrl}
            currentContent={currentContent}
          />
        }
        quizContent={quizContent}
        chatPanel={
          <LazyStudyAssistantChat
            courseId={courseId}
            open={chatOpen}
            onClose={onCloseChat}
            onCitationNavigate={onCitationNavigate}
          />
        }
        className="h-dvh gaze-display-locked"
      />

      <GazeDotOverlay
        visible={showGazeDot}
        gazeDot={gazeDot}
        activeLessonId={activeLessonId}
        currentSlide={currentSlide}
      />

      <CameraPreview stream={cameraPreviewStream} visible={showCameraPreview} />

      <DisplayGuardOverlay
        blocked={displayGuard.blocked}
        reason={displayGuard.reason}
        zoomPercent={displayGuard.zoomPercent}
        onRecheck={displayGuard.recheck}
      />
    </>
  );
}

function GazeDotOverlay({
  visible,
  gazeDot,
  activeLessonId,
  currentSlide,
}: {
  visible: boolean;
  gazeDot: GazeDotPosition | null;
  activeLessonId: string;
  currentSlide: number;
}) {
  if (!visible || !isGazeDotVisible(gazeDot, activeLessonId, currentSlide)) {
    return null;
  }

  return (
    <div className="pointer-events-none fixed inset-0 z-30">
      <span
        className="absolute size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-black shadow-[0_1px_5px_rgba(0,0,0,0.2)]"
        style={{ left: `${gazeDot.x * 100}%`, top: `${gazeDot.y * 100}%` }}
      />
    </div>
  );
}
