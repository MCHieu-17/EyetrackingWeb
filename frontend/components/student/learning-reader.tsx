"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { useGazeTracker, type GazeFrameResult } from "@/hooks/use-gaze-tracker";
import { useAoiSnapshot } from "@/hooks/use-aoi-snapshot";
import {
  useCourseOutline,
  useLessonSlides,
  useMyEnrollments,
} from "@/hooks/use-student";
import {
  createLearningSession,
  endLearningSession,
  getDeviceFingerprint,
  type GazeBatchInput,
  type GazeSample,
} from "@/lib/api/student";
import { flushGazeQueue, queueGazeBatch } from "@/lib/gaze-sender";
import { createPresentation } from "@/lib/api/aoi";
import {
  getCalibrationScreenSnapshot,
  getStoredGazeSessionId,
  subscribeCalibrationScreen,
} from "@/lib/api/calibration";
import { resolveMediaUrl } from "@/lib/api/client";
import { LazyInlineQuiz } from "@/components/quiz/lazy-inline-quiz";
import { LazyPdfPage } from "@/components/pdf/lazy-pdf-page";
import { ReaderFrame } from "@/components/reader/reader-frame";
import { useChatAccess } from "@/hooks/use-chat";
import { LazyStudyAssistantChat } from "@/components/assistant/lazy-study-assistant-chat";
import {
  AssistantProvider,
  useAssistant,
} from "@/components/assistant/assistant-context";

// Gom gaze sample rồi gửi theo batch — tránh vượt rate limit 60 req/phút của backend
// (tracker phát ~12 điểm/giây; gửi lẻ từng điểm sẽ chạm trần gần như ngay lập tức).
const GAZE_FLUSH_MS = 1500;
const GAZE_MAX_BATCH = 40;

function hashPayload(value: unknown): string {
  const text = JSON.stringify(value);
  let h1 = 0x811c9dc5;
  let h2 = 0x01000193;
  for (let i = 0; i < text.length; i += 1) {
    const code = text.charCodeAt(i);
    h1 = Math.imul(h1 ^ code, 0x01000193) >>> 0;
    h2 = Math.imul(h2 ^ code, 0x85ebca6b) >>> 0;
  }
  return (
    h1.toString(16).padStart(8, "0").repeat(4) +
    h2.toString(16).padStart(8, "0").repeat(4)
  );
}

export function LearningReader({ courseId }: { courseId: string }) {
  return (
    <AssistantProvider>
      <ReaderContent courseId={courseId} />
    </AssistantProvider>
  );
}

function ReaderContent({ courseId }: { courseId: string }) {
  const searchParams = useSearchParams();
  const requestedLessonId = searchParams.get("lesson");

  const { data: course, isLoading: courseLoading, isError: courseError, refetch } =
    useCourseOutline(courseId);
  const { data: enrollments = [] } = useMyEnrollments();

  const [activeLessonId, setActiveLessonId] = useState(requestedLessonId ?? "");
  const [currentSlide, setCurrentSlide] = useState(0);
  const [learningSessionIds, setLearningSessionIds] = useState<Record<string, string>>({});
  const [trackingLessons, setTrackingLessons] = useState<Record<string, boolean>>({});
  // Phiên hiệu chỉnh đọc thẳng từ localStorage ngay lần render đầu (client):
  // bài tập không tạo phiên học nên không thể dựa vào callback tạo phiên để biết
  // đã hiệu chỉnh hay chưa. Chỉ dùng cho effect của useGazeTracker nên không gây
  // lệch hydration.
  const [gazeCalibrated, setGazeCalibrated] = useState(() =>
    Boolean(getStoredGazeSessionId()),
  );
  // Vị trí chấm điểm nhìn (chuẩn hóa theo màn hình) khi GV bật hiển thị cho SV.
  // `key` = bài+trang lúc ghi, để tự ẩn khi đổi trang/bài mà không cần effect.
  const [gazeDot, setGazeDot] = useState<{ x: number; y: number; key: string } | null>(null);
  // Chat dock bên phải. Chỉ dùng ở desktop (>= xl); mobile không thiết kế.
  const [chatOpen, setChatOpen] = useState(false);
  const { setReaderMode, setReaderLessonId, mode: assistantMode, assignmentId: assistantAssignmentId } = useAssistant();
  const chatAccess = useChatAccess(courseId, chatOpen || assistantMode === "quiz");
  const chatAllowed = chatAccess.data?.allowed === true && !chatAccess.isError;
  const refreshChatAccess = chatAccess.refetch;
  useEffect(() => {
    void refreshChatAccess();
  }, [activeLessonId, assistantAssignmentId, assistantMode, refreshChatAccess]);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (!chatAllowed) setChatOpen(false);
  }, [chatAllowed]);
  const assistantButtonRef = useRef<HTMLButtonElement>(null);
  const wasChatOpen = useRef(false);

  const gazeBufferRef = useRef<GazeSample[]>([]);
  const gazeBufferLessonRef = useRef<string | null>(null);
  const flushTimerRef = useRef<number>(0);
  const sessionsRef = useRef<Record<string, string>>({});
  const aoiSnapshotIdRef = useRef<string | null>(null);
  const aoiReadyRef = useRef(false);
  const layoutKeyRef = useRef("reader");
  const [presentationId, setPresentationId] = useState<string | null>(null);
  const presentationIdRef = useRef<string | null>(null);
  const presentationSequenceRef = useRef(0);
  const layoutGenerationRef = useRef(0);
  const batchNoRef = useRef<Record<string, number>>({});

  const allItems = useMemo(
    () => course?.modules.flatMap((module) => module.lessons) ?? [],
    [course],
  );
  const flatLessonIndex = allItems.findIndex((lesson) => lesson.id === activeLessonId);
  const nextLesson = allItems[flatLessonIndex + 1];

  const requestedIsValid =
    !!requestedLessonId && allItems.some((lesson) => lesson.id === requestedLessonId);
  const activeLessonIsValid = allItems.some((lesson) => lesson.id === activeLessonId);
  const resolvedLessonId =
    allItems.length === 0
      ? activeLessonId
      : requestedIsValid
        ? (requestedLessonId as string)
        : activeLessonIsValid
          ? activeLessonId
          : allItems[0].id;

  // Render-phase adjust: tự chọn bài khi outline tải xong mà chưa có bài hợp lệ.
  if (course && allItems.length > 0 && resolvedLessonId !== activeLessonId) {
    setActiveLessonId(resolvedLessonId);
  }

  const activeModule = useMemo(
    () =>
      course?.modules.find((module) =>
        module.lessons.some((lesson) => lesson.id === activeLessonId),
      ) ?? course?.modules[0],
    [course, activeLessonId],
  );

  const activeLesson = useMemo(
    () =>
      activeModule?.lessons.find((lesson) => lesson.id === activeLessonId) ??
      activeModule?.lessons[0],
    [activeModule, activeLessonId],
  );

  const activeIsQuiz = activeLesson?.kind === "quiz";
  const activeQuizId = activeLesson?.quizId ?? "";
  // Cờ điểm nhìn thuộc KHÓA HỌC: bật là áp cho mọi bài giảng VÀ bài tập.
  const showGazeDot = Boolean(course?.showGazeDot);
  // Khóa tắt bắt buộc hiệu chỉnh -> không bật camera, không ghi gaze.
  const calibrationRequired = course?.requireCalibration !== false;
  // Viewport lúc calibration (localStorage). Dùng useSyncExternalStore để
  // không đọc localStorage trong render gây lệch hydration.
  const calibrationScreen = useSyncExternalStore(
    subscribeCalibrationScreen,
    getCalibrationScreenSnapshot,
    () => null,
  );
  // Chỉ tạo phiên học khi đã có dữ liệu khóa (tránh tạo với consent mặc định).
  const courseReady = Boolean(course);

  // Đồng bộ ngữ cảnh chat: reader thường / quiz. InlineQuiz sẽ override bằng
  // assignmentId + mode quiz/review khi mount.
  useEffect(() => {
    setReaderMode(activeIsQuiz ? "quiz" : "reader");
  }, [activeIsQuiz, setReaderMode]);

  useEffect(() => {
    setReaderLessonId(activeLessonId || null);
  }, [activeLessonId, setReaderLessonId]);

  // Đóng chat thì trả focus về nút "Trợ lý" ở header.
  useEffect(() => {
    if (wasChatOpen.current && !chatOpen) {
      assistantButtonRef.current?.focus();
    }
    wasChatOpen.current = chatOpen;
  }, [chatOpen]);

  const enrollmentId = enrollments.find((enrollment) => enrollment.course.id === courseId)?.enrollmentId;

  // Flush đúng batch của bài/phiên cũ trước khi phiên bị đóng.
  const flushGazeForLesson = useCallback((lessonId: string, sessionId?: string, keepalive = false) => {
    if (gazeBufferLessonRef.current !== lessonId) return;
    const sid = sessionId ?? sessionsRef.current[lessonId];
    const buf = gazeBufferRef.current;
    const presentation = presentationIdRef.current;
    if (!sid || !presentation || buf.length === 0) return;
    gazeBufferRef.current = [];
    gazeBufferLessonRef.current = null;
    const batchNo = batchNoRef.current[sid] ?? 0;
    batchNoRef.current[sid] = batchNo + 1;
    const sequences = buf.map((sample) => sample.sequence);
    const input: GazeBatchInput = {
      batchId: globalThis.crypto?.randomUUID?.() ?? `batch-${Date.now()}-${batchNo}`,
      batchNo,
      presentationId: presentation,
      layoutSnapshotId: aoiSnapshotIdRef.current,
      sequenceStart: Math.min(...sequences),
      sequenceEnd: Math.max(...sequences),
      payloadHash: hashPayload(buf),
      samples: buf,
    };
    void queueGazeBatch(sid, input, keepalive);
  }, []);

  const closeLearningSession = useCallback((lessonId: string, expectedSessionId?: string, keepalive = false) => {
    const sessionId = sessionsRef.current[lessonId];
    if (!sessionId || (expectedSessionId && sessionId !== expectedSessionId)) return;

    flushGazeForLesson(lessonId, sessionId, keepalive);
    delete sessionsRef.current[lessonId];
    setLearningSessionIds((prev) => {
      if (prev[lessonId] !== sessionId) return prev;
      const next = { ...prev };
      delete next[lessonId];
      return next;
    });
    endLearningSession(sessionId, "completed", keepalive).catch(() => {});
  }, [flushGazeForLesson]);

  // Mỗi lần vào bài tạo một phiên mới; phiên đã đóng bị xóa khỏi cả ref và state.
  // Bài tập trắc nghiệm cũng có phiên: gaze của bài tập được ghi thô theo viewport
  // (surface='quiz', không có slide).
  useEffect(() => {
    if (
      !courseReady ||
      !activeLessonId ||
      !enrollmentId ||
      sessionsRef.current[activeLessonId]
    ) {
      return;
    }

    const lessonId = activeLessonId;
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const calibrationWidth = calibrationScreen?.w ?? viewportWidth;
    const calibrationHeight = calibrationScreen?.h ?? viewportHeight;

    let cancelled = false;
    createLearningSession({
      enrollmentId,
      lessonId,
      deviceFingerprint: getDeviceFingerprint(),
      viewportWidthPx: viewportWidth,
      viewportHeightPx: viewportHeight,
      calibrationWidthPx: calibrationWidth,
      calibrationHeightPx: calibrationHeight,
      devicePixelRatio: window.devicePixelRatio || 1,
      // Khóa tắt bắt buộc hiệu chỉnh -> không xin consent ghi gaze.
      trackingConsent: calibrationRequired,
    })
      .then((session) => {
        if (cancelled) {
          endLearningSession(session.id, "completed").catch(() => {});
          return;
        }
        sessionsRef.current[lessonId] = session.id;
        setLearningSessionIds((prev) => ({ ...prev, [lessonId]: session.id }));
        setTrackingLessons((prev) => ({ ...prev, [lessonId]: session.trackingConsent }));
        setGazeCalibrated(Boolean(getStoredGazeSessionId()));
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [
    courseReady,
    activeLessonId,
    enrollmentId,
    closeLearningSession,
    calibrationRequired,
    calibrationScreen,
  ]);

  useEffect(() => {
    void flushGazeQueue();
  }, []);

  const previousLessonRef = useRef<string | null>(null);
  useEffect(() => {
    const previous = previousLessonRef.current;
    if (previous && previous !== activeLessonId) {
      closeLearningSession(previous);
    }
    previousLessonRef.current = activeLessonId;
  }, [activeLessonId, closeLearningSession]);

  const learningSessionId = learningSessionIds[activeLessonId];
  const { data: slides = [], isLoading: slidesLoading } = useLessonSlides(
    activeIsQuiz ? "" : activeLessonId,
    learningSessionId,
  );
  const total = slides.length;
  // Render-phase adjust: đổi bài có ít slide hơn → quay về slide đầu.
  if (total > 0 && currentSlide > total - 1) setCurrentSlide(0);
  const currentContent = slides[currentSlide];

  const slidePdfUrl = useMemo(
    () => resolveMediaUrl(currentContent?.pdfUrl),
    [currentContent],
  );

  // Chỉ thu gaze khi khóa bật theo dõi VÀ backend cho phép (trackingConsent=true).
  const trackingAllowed =
    calibrationRequired &&
    Boolean(activeLessonId) &&
    trackingLessons[activeLessonId] !== false;

  const flushGaze = useCallback(() => {
    flushGazeForLesson(activeLessonId);
  }, [activeLessonId, flushGazeForLesson]);

  // Trước khi đo layout mới: dừng nhận sample + flush batch cũ ngay lập tức,
  // tránh sample bị gán sang snapshot mới.
  const pauseAndFlushGaze = useCallback(() => {
    aoiReadyRef.current = false;
    flushGazeForLesson(activeLessonId);
  }, [activeLessonId, flushGazeForLesson]);

  // Layout key đổi khi mở/đóng chat để snapshot AOI phản ánh đúng bố cục.
  const layoutKey = activeIsQuiz
    ? chatOpen
      ? "quiz-chat"
      : "quiz"
    : chatOpen
      ? "reader-chat"
      : "reader";

  useEffect(() => {
    layoutKeyRef.current = layoutKey;
  }, [layoutKey]);

  // Mỗi slide/quiz là một presentation riêng. Đổi presentation phải flush
  // batch cũ trước để batch không trộn context.
  const presentationKeyRef = useRef("");
  useEffect(() => {
    if (!learningSessionId || !activeLessonId) return;
    if (!activeIsQuiz && !slides[currentSlide]) return;
    const key = `${learningSessionId}:${activeLessonId}:${activeIsQuiz ? "quiz" : currentSlide}`;
    if (presentationKeyRef.current === key) return;
    presentationKeyRef.current = key;
    flushGazeForLesson(activeLessonId);
    const sequenceNo = presentationSequenceRef.current;
    presentationSequenceRef.current += 1;
    createPresentation(learningSessionId, {
      lessonVersionSlideId: activeIsQuiz ? null : slides[currentSlide]?.id ?? null,
      surface: activeIsQuiz ? "quiz" : "lesson",
      sequenceNo,
    })
      .then((presentation) => {
        presentationIdRef.current = presentation.id;
        setPresentationId(presentation.id);
      })
      .catch(() => {
        presentationIdRef.current = null;
        setPresentationId(null);
      });
  }, [
    learningSessionId,
    activeLessonId,
    activeIsQuiz,
    currentSlide,
    slides,
    flushGazeForLesson,
  ]);

  // Đo layout DOM và tạo snapshot AOI. Tạm dừng ghi gaze trong lúc đo để
  // sample không bị gán sang layout mới.
  const aoiSnapshot = useAoiSnapshot({
    sessionId: learningSessionId ?? null,
    presentationId,
    enabled: Boolean(
      learningSessionId && presentationId && trackingAllowed && (total > 0 || activeIsQuiz),
    ),
    layoutKey,
    onBeforeSnapshot: pauseAndFlushGaze,
  });

  useEffect(() => {
    aoiSnapshotIdRef.current = aoiSnapshot.snapshotId;
    aoiReadyRef.current = aoiSnapshot.ready;
    layoutGenerationRef.current = aoiSnapshot.layoutGeneration;
  }, [aoiSnapshot.snapshotId, aoiSnapshot.ready, aoiSnapshot.layoutGeneration]);

  const enqueueGaze = useCallback(
    (sample: GazeSample) => {
      if (gazeBufferLessonRef.current && gazeBufferLessonRef.current !== activeLessonId) {
        flushGazeForLesson(gazeBufferLessonRef.current);
      }
      gazeBufferLessonRef.current = activeLessonId;
      gazeBufferRef.current.push(sample);
      if (gazeBufferRef.current.length >= GAZE_MAX_BATCH) {
        flushGaze();
      }
    },
    [activeLessonId, flushGaze, flushGazeForLesson],
  );

  useEffect(() => {
    if (!learningSessionId) return;
    flushTimerRef.current = window.setInterval(flushGaze, GAZE_FLUSH_MS);
    return () => {
      window.clearInterval(flushTimerRef.current);
      flushGaze();
    };
  }, [learningSessionId, flushGaze]);

  const { source: gazeSource } = useGazeTracker({
    // Bài giảng: cần có slide. Bài tập: không có slide nhưng vẫn thu gaze.
    enabled: Boolean(
      activeLessonId && trackingAllowed && (total > 0 || activeIsQuiz),
    ),
    calibrated: gazeCalibrated,
    allowSimulation: false,
    getContext: () => ({
      presentationId: presentationIdRef.current,
      layoutGeneration: layoutGenerationRef.current,
      surface: activeIsQuiz ? "quiz" : "lesson",
    }),
    onPoint: useCallback(
      (x: number, y: number, source: string) => {
        if (source !== "real") return;
        const faceDetected = !(x === -1 && y === -1);
        if (showGazeDot) {
          if (!faceDetected) setGazeDot(null);
          else setGazeDot({ x, y, key: `${activeLessonId}:${currentSlide}` });
        }
      },
      [showGazeDot, activeLessonId, currentSlide],
    ),
    onFrame: useCallback(
      (frame: GazeFrameResult) => {
        if (!learningSessionId || !trackingAllowed) return;
        if (!aoiReadyRef.current || !presentationIdRef.current) return;
        const faceDetected = frame.status === "ok";
        enqueueGaze({
          sequence: frame.sequence ?? 0,
          captureMonotonicNs:
            frame.captureMonotonicNs ?? Math.round(performance.now() * 1e6),
          eventTime: frame.eventTime,
          viewportX: faceDetected ? frame.x : null,
          viewportY: faceDetected ? frame.y : null,
          status: frame.status,
          qualityFlags: {},
        });
      },
      [learningSessionId, trackingAllowed, enqueueGaze],
    ),
  });

  // Điều hướng bàn phím
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "ArrowRight") {
        setCurrentSlide((value) => Math.min(Math.max(total - 1, 0), value + 1));
      }
      if (event.key === "ArrowLeft") {
        setCurrentSlide((value) => Math.max(0, value - 1));
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [total]);

  // Đóng mọi phiên còn sống khi rời trang. closeLearningSession xóa ID trước khi gọi API.
  useEffect(() => {
    const closeAll = (keepalive = false) => {
      for (const lessonId of Object.keys(sessionsRef.current)) {
        closeLearningSession(lessonId, undefined, keepalive);
      }
    };
    const onBeforeUnload = () => {
      closeAll(true);
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload);
      closeAll();
    };
  }, [closeLearningSession]);

  const selectLesson = (lessonId: string) => {
    // Đóng phiên bài cũ trước khi chuyển
    if (activeLessonId !== lessonId) closeLearningSession(activeLessonId);
    setActiveLessonId(lessonId);
    setCurrentSlide(0);
  };

  const closeChat = useCallback(() => setChatOpen(false), []);

  if (courseLoading) {
    return (
      <div className="flex h-dvh flex-col overflow-hidden bg-[#f5f6f2] p-2 sm:p-3">
        <div className="flex h-12 shrink-0 items-center px-3">
          <Skeleton className="h-7 w-28 rounded-full" />
        </div>
        <div className="flex min-h-0 flex-1 gap-3">
           <Skeleton className="hidden w-64 shrink-0 rounded-[20px] lg:block" />
          <div className="flex min-w-0 flex-1 items-center justify-center p-3">
             <Skeleton className="aspect-video w-full max-w-5xl rounded-[18px]" />
          </div>
        </div>
      </div>
    );
  }

  if (courseError || !course) {
    return (
      <div className="flex h-dvh items-center justify-center p-6">
        <ErrorState
          title="Không tải được bài học"
          description="Vui lòng kiểm tra kết nối và thử lại."
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  const banners = (
    <>
      {gazeSource === "off" && calibrationRequired && (total > 0 || activeIsQuiz) && (
        <div className="z-10 shrink-0 px-4 pb-2 sm:px-5">
          <div className="mx-auto flex max-w-[1400px] flex-col gap-2 rounded-xl border border-[#dce8d9] bg-[#e8f1e6] px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs leading-5 text-foreground">
              Không kết nối được phiên theo dõi điểm nhìn (phiên hiệu chỉnh có thể đã hết hạn). Nội
              dung vẫn dùng được bình thường, nhưng dữ liệu gaze sẽ không được ghi nhận.
            </p>
            <Button asChild size="sm" variant="outline" className="shrink-0">
              <Link
                href={`/student/courses/${courseId}/prepare${activeLessonId ? `?lesson=${encodeURIComponent(activeLessonId)}` : ""}`}
              >
                Kiểm tra &amp; hiệu chỉnh lại
              </Link>
            </Button>
          </div>
        </div>
      )}
    </>
  );

  const slideContent = slidesLoading ? (
    <Skeleton className="aspect-video w-full rounded-2xl" />
  ) : slidePdfUrl ? (
    <div
      data-aoi="slide"
      className="relative aspect-video overflow-hidden rounded-[18px] border border-border/80 bg-white shadow-sm"
    >
      <LazyPdfPage
        key={`${slidePdfUrl}:${currentContent?.pageNumber ?? 1}`}
        url={slidePdfUrl}
        pageNumber={currentContent?.pageNumber ?? 1}
        alt={currentContent?.title ?? "Trang bài học"}
        className="absolute inset-0"
      />
    </div>
  ) : (
    <div className="flex aspect-video flex-col items-center justify-center rounded-[18px] border border-border/80 bg-white p-8 text-center shadow-sm">
      <div className="flex size-11 items-center justify-center rounded-full bg-muted text-foreground">
        <Icon name="ri-image-line" className="size-5" />
      </div>
      <p className="mt-4 max-w-sm text-base font-semibold text-foreground sm:text-lg">
        {currentContent?.title ?? "Nội dung bài học"}
      </p>
      <p className="mt-2 text-sm text-muted-foreground">
        Nội dung trang PDF sẽ hiển thị tại đây.
      </p>
    </div>
  );

  const quizContent = activeQuizId ? (
    <LazyInlineQuiz
      quizId={activeQuizId}
      onNext={nextLesson ? () => selectLesson(nextLesson.id) : undefined}
      hasNext={Boolean(nextLesson)}
    />
  ) : (
    <p className="p-8 text-center text-sm text-muted-foreground">
      Bài tập chưa sẵn sàng.
    </p>
  );

  const toggleChat = async () => {
    if (chatOpen) {
      setChatOpen(false);
      return;
    }
    const result = await chatAccess.refetch();
    if (result.data?.allowed && !result.isError) setChatOpen(true);
  };

  return (
    <>
      <ReaderFrame
        courseTitle={course.title}
        modules={course.modules}
        activeLessonId={activeLessonId}
        activeLesson={activeLesson ?? null}
        activeModule={activeModule ?? null}
        slides={slides}
        currentSlide={currentSlide}
        activeIsQuiz={activeIsQuiz}
        chatOpen={chatOpen}
        chatAllowed={chatAllowed}
        chatButtonRef={assistantButtonRef}
        chatReason={
          chatAccess.data?.reason ??
          (chatAccess.isError ? "Không kiểm tra được quyền dùng chatbot" : null)
        }
        onToggleChat={toggleChat}
        onSelectLesson={selectLesson}
        onPrevSlide={() => setCurrentSlide((value) => Math.max(0, value - 1))}
        onNextSlide={() =>
          setCurrentSlide((value) => Math.min(Math.max(total - 1, 0), value + 1))
        }
        gazeSource={gazeSource}
        calibrationRequired={calibrationRequired}
        banners={banners}
        slideContent={slideContent}
        quizContent={quizContent}
        chatPanel={
          <LazyStudyAssistantChat
            courseId={courseId}
            open={chatOpen}
            onClose={closeChat}
          />
        }
        className="h-dvh"
      />

      {showGazeDot && gazeDot && gazeDot.key === `${activeLessonId}:${currentSlide}` && (
        <div className="pointer-events-none fixed inset-0 z-30">
          <span
            className="absolute size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-black shadow-[0_1px_5px_rgba(0,0,0,0.2)]"
            style={{ left: `${gazeDot.x * 100}%`, top: `${gazeDot.y * 100}%` }}
          />
        </div>
      )}
    </>
  );
}
