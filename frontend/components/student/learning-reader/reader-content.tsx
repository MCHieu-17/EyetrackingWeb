"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { useSearchParams } from "next/navigation";
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
import { ReaderFrame } from "@/components/reader/reader-frame";
import { LazyStudyAssistantChat } from "@/components/assistant/lazy-study-assistant-chat";
import { useAssistant } from "@/components/assistant/assistant-context";
import { ReaderBanners } from "./reader-banners";
import { ReaderError, ReaderLoading } from "./reader-states";
import { ReaderSlideContent } from "./reader-slide-content";
import { useReaderChat } from "./use-reader-chat";
import {
  findNextLesson,
  getReaderLayoutKey,
  hashPayload,
  isGazeDotVisible,
  resolveActiveLessonId,
  type GazeDotPosition,
} from "./reader-helpers";

// Gom gaze sample rồi gửi theo batch — tránh vượt rate limit 60 req/phút của backend
// (tracker phát ~12 điểm/giây; gửi lẻ từng điểm sẽ chạm trần gần như ngay lập tức).
const GAZE_FLUSH_MS = 1500;
const GAZE_MAX_BATCH = 40;

export function ReaderContent({ courseId }: { courseId: string }) {
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
  const [gazeDot, setGazeDot] = useState<GazeDotPosition | null>(null);
  const { setReaderMode, setReaderLessonId, mode: assistantMode, assignmentId: assistantAssignmentId } = useAssistant();
  const {
    chatOpen,
    chatAllowed,
    chatAccess,
    assistantButtonRef,
    toggleChat,
    closeChat,
  } = useReaderChat({
    courseId,
    activeLessonId,
    assistantMode,
    assistantAssignmentId,
  });

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
  const nextLesson = findNextLesson(allItems, activeLessonId);

  const resolvedLessonId = resolveActiveLessonId({
    requestedLessonId,
    activeLessonId,
    lessons: allItems,
  });

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
  const layoutKey = getReaderLayoutKey(activeIsQuiz, chatOpen);

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

  if (courseLoading) {
    return <ReaderLoading />;
  }

  if (courseError || !course) {
    return <ReaderError onRetry={() => refetch()} />;
  }

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
        banners={
          <ReaderBanners
            courseId={courseId}
            activeLessonId={activeLessonId}
            calibrationRequired={calibrationRequired}
            gazeSource={gazeSource}
            hasContent={total > 0 || activeIsQuiz}
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
            onClose={closeChat}
          />
        }
        className="h-dvh"
      />

      {showGazeDot && isGazeDotVisible(gazeDot, activeLessonId, currentSlide) && (
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
