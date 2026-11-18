"use client";

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { useSearchParams } from "next/navigation";
import { useGazeTracker, type GazeFrameResult } from "@/hooks/use-gaze-tracker";
import { useAoiSnapshot } from "@/hooks/use-aoi-snapshot";
import { useCourseVisit } from "@/hooks/use-course-visit";
import { useDisplayGuard } from "@/hooks/use-display-guard";
import {
  useCourseOutline,
  useLessonSlides,
  useMyEnrollments,
} from "@/hooks/use-student";
import { useRuntimeConfig } from "@/hooks/use-runtime-config";
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
  isFrameForActiveContext,
  isValidGazeSequence,
} from "@/lib/gaze/frame-protocol";
import {
  createPresentationRequestTracker,
  presentationContextKey,
  presentationEntryFor,
  type PresentationEntry,
} from "@/lib/gaze/presentation-context";
import {
  getCalibrationScreenSnapshot,
  getStoredGazeSessionId,
  subscribeCalibrationScreen,
} from "@/lib/api/calibration";
import { resolveMediaUrl } from "@/lib/api/client";
import type { ChatCitation } from "@/lib/api/chat";
import { useAssistant } from "@/components/assistant/assistant-context";
import { ReaderError, ReaderLoading } from "./reader-states";
import { ReaderView } from "./reader-view";
import { useReaderChat } from "./use-reader-chat";
import {
  findCitationSlideIndex,
  findNextLesson,
  getNextSlideIndex,
  getPreviousSlideIndex,
  getReaderLayoutKey,
  resolveActiveLessonId,
  type GazeDotPosition,
} from "./reader-helpers";

// Gom gaze sample rồi gửi theo batch — tránh vượt rate limit 120 req/phút của backend
// (tracker phát theo GAZE_FPS, tối đa 60 điểm/giây; gửi lẻ từng điểm sẽ chạm trần ngay).
// Ở 60 FPS, 40 sample/batch ≈ 90 req/phút nên vẫn dưới ngưỡng.
const GAZE_FLUSH_MS = 1500;
const GAZE_MAX_BATCH = 40;

export function ReaderContent({ courseId }: { courseId: string }) {
  const searchParams = useSearchParams();
  const requestedLessonId = searchParams.get("lesson");

  const { data: course, isLoading: courseLoading, isError: courseError, refetch } =
    useCourseOutline(courseId);
  const { data: enrollments = [] } = useMyEnrollments();
  // FPS ghi gaze lấy runtime từ backend; lỗi/đang tải thì dùng fallback 15.
  const { gazeFps } = useRuntimeConfig();

  const [activeLessonId, setActiveLessonId] = useState(requestedLessonId ?? "");
  const [currentSlide, setCurrentSlide] = useState(0);
  // Citation đang chờ slide của bài mới tải xong (khi citation trỏ sang bài khác).
  const [pendingCitation, setPendingCitation] = useState<ChatCitation | null>(null);
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
  // Presentation/layout tại thời điểm sample đầu tiên vào buffer. Giữ riêng
  // để batch cuối vẫn gắn đúng lượt xem cũ kể cả khi refs presentation đã bị
  // reset (đổi slide nhanh, unmount, đóng phiên).
  const gazeBatchOwnerRef = useRef<{
    presentationId: string;
    layoutId: string | null;
  } | null>(null);
  const flushTimerRef = useRef<number>(0);
  const sessionsRef = useRef<Record<string, string>>({});
  const aoiSnapshotIdRef = useRef<string | null>(null);
  const aoiReadyRef = useRef(false);
  const layoutKeyRef = useRef("reader");
  const [presentationId, setPresentationId] = useState<string | null>(null);
  const presentationIdRef = useRef<string | null>(null);
  const activePresentationKeyRef = useRef<string | null>(null);
  const presentationRequestRef = useRef(createPresentationRequestTracker());
  const presentationEntryRef = useRef<PresentationEntry | null>(null);
  const presentationSequenceRef = useRef(0);
  const layoutGenerationRef = useRef(0);

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
  const { visitId: courseVisitId } = useCourseVisit({
    courseId,
    enrollmentId: enrollmentId ?? null,
  });

  // Flush đúng batch của bài/phiên cũ trước khi phiên bị đóng. Trả Promise
  // của lần enqueue để closeLearningSession chờ batch cuối vào queue.
  const flushGazeForLesson = useCallback(
    (
      lessonId: string,
      sessionId?: string,
      keepalive = false,
    ): Promise<void> => {
      if (gazeBufferLessonRef.current !== lessonId) return Promise.resolve();
      const sid = sessionId ?? sessionsRef.current[lessonId];
      const buf = gazeBufferRef.current;
      const owner = gazeBatchOwnerRef.current;
      // Ưu tiên presentation/layout lúc sample được ghi; fallback refs hiện
      // tại cho luồng cũ trước khi buffer kịp có owner.
      const presentation = owner?.presentationId ?? presentationIdRef.current;
      const layoutId = owner ? owner.layoutId : aoiSnapshotIdRef.current;
      if (!sid || !presentation) {
        // Không có presentation/session hợp lệ: bỏ buffer thay vì gán nhầm
        // sample sang presentation kế tiếp.
        gazeBufferRef.current = [];
        gazeBufferLessonRef.current = null;
        gazeBatchOwnerRef.current = null;
        return Promise.resolve();
      }
      if (buf.length === 0) {
        gazeBufferLessonRef.current = null;
        gazeBatchOwnerRef.current = null;
        return Promise.resolve();
      }
      gazeBufferRef.current = [];
      gazeBufferLessonRef.current = null;
      gazeBatchOwnerRef.current = null;
      const sequences = buf.map((sample) => sample.sequence);
      const input: GazeBatchInput = {
        batchId: globalThis.crypto?.randomUUID?.() ?? `batch-${Date.now()}`,
        presentationId: presentation,
        layoutId,
        sequenceStart: Math.min(...sequences),
        sequenceEnd: Math.max(...sequences),
        samples: buf,
      };
      return queueGazeBatch(sid, input, keepalive).catch(() => {});
    },
    [],
  );

  const closeLearningSession = useCallback(
    (lessonId: string, expectedSessionId?: string, keepalive = false) => {
      const sessionId = sessionsRef.current[lessonId];
      if (!sessionId || (expectedSessionId && sessionId !== expectedSessionId)) return;

      const flushed = flushGazeForLesson(lessonId, sessionId, keepalive);
      delete sessionsRef.current[lessonId];
      setLearningSessionIds((prev) => {
        if (prev[lessonId] !== sessionId) return prev;
        const next = { ...prev };
        delete next[lessonId];
        return next;
      });

      // Unload: gửi keepalive rồi đi ngay, không chờ flush.
      if (keepalive) {
        endLearningSession(sessionId, "completed", true).catch(() => {});
        return;
      }

      // Best-effort: chờ batch cuối vào queue + flush tối đa 1.5s rồi mới
      // đóng session để backend kịp gắn sample vào presentation cũ.
      void (async () => {
        await Promise.race([
          flushed.then(() => flushGazeQueue(sessionId)),
          new Promise<void>((resolve) => window.setTimeout(resolve, 1500)),
        ]).catch(() => {});
        await endLearningSession(sessionId, "completed").catch(() => {});
      })();
    },
    [flushGazeForLesson],
  );

  // Mỗi lần vào bài tạo một phiên mới; phiên đã đóng bị xóa khỏi cả ref và state.
  // Bài tập trắc nghiệm cũng có phiên: gaze của bài tập được ghi thô theo viewport
  // (surface='quiz', không có slide).
  useEffect(() => {
    if (
      !courseReady ||
      !activeLessonId ||
      !enrollmentId ||
      !courseVisitId ||
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
      courseVisitId,
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
          // StrictMode/route transition có thể mount lại và nhận đúng session
          // này từ server; đợi một nhịp rồi chỉ đóng nếu không ai adopt.
          window.setTimeout(() => {
            if (sessionsRef.current[lessonId] !== session.id) {
              endLearningSession(session.id, "completed").catch(() => {});
            }
          }, 2000);
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
    courseVisitId,
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
  // Citation trỏ sang bài khác: chờ slide của bài mới tải xong rồi nhảy tới.
  if (
    pendingCitation &&
    pendingCitation.lessonId === activeLessonId &&
    !slidesLoading
  ) {
    const index = findCitationSlideIndex(pendingCitation, slides);
    if (index >= 0 && index !== currentSlide) setCurrentSlide(index);
    setPendingCitation(null);
  }
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

  // Trang đọc là trang gaze-critical: zoom/fullscreen làm lệch toạ độ. Guard
  // chỉ bật khi thực sự đang ghi gaze để không chặn oan lúc khóa tắt theo dõi.
  const displayGuard = useDisplayGuard({
    enabled: trackingAllowed,
    mode: "reader",
  });
  const displayBlocked = displayGuard.blocked;

  const flushGaze = useCallback(() => {
    flushGazeForLesson(activeLessonId);
  }, [activeLessonId, flushGazeForLesson]);

  // Flush buffer của đúng bài đang giữ sample (có thể là bài cũ trong lúc
  // chuyển bài) trước khi invalidate presentation.
  const flushPendingGaze = useCallback(() => {
    const lessonId = gazeBufferLessonRef.current;
    if (lessonId) flushGazeForLesson(lessonId);
  }, [flushGazeForLesson]);

  // Trước khi đo layout mới: dừng nhận sample + flush batch cũ ngay lập tức,
  // tránh sample bị gán sang snapshot mới.
  const pauseAndFlushGaze = useCallback(() => {
    aoiReadyRef.current = false;
    flushPendingGaze();
  }, [flushPendingGaze]);

  // Khi guard phát hiện zoom/fullscreen: đóng băng nhận sample và flush batch
  // đang giữ ngay lập tức. useGazeTracker/useAoiSnapshot cũng bị tắt bên dưới.
  useEffect(() => {
    if (displayBlocked) pauseAndFlushGaze();
  }, [displayBlocked, pauseAndFlushGaze]);

  // Resize làm toạ độ gaze và rect DOM đổi cùng lúc. Tạm dừng ngay thay vì
  // chờ snapshot mới (debounce 250ms) để không map sample bằng layout cũ.
  useEffect(() => {
    if (!trackingAllowed) return;
    const onResize = () => pauseAndFlushGaze();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [pauseAndFlushGaze, trackingAllowed]);

  // Layout key đổi khi mở/đóng chat để snapshot AOI phản ánh đúng bố cục.
  const layoutKey = getReaderLayoutKey(activeIsQuiz, chatOpen);

  useEffect(() => {
    layoutKeyRef.current = layoutKey;
  }, [layoutKey]);

  // Mỗi slide/quiz là một presentation riêng. Đổi context phải flush batch cũ
  // TRƯỚC khi vô hiệu hoá presentation, sau đó chặn mọi frame cũ bằng key +
  // request token. Dùng layout effect để refs đổi trước khi timer camera chạy.
  const presentationKeyRef = useRef<string | null>(null);
  useLayoutEffect(() => {
    const surface = activeIsQuiz ? "quiz" : "lesson";
    const slide = activeIsQuiz ? null : slides[currentSlide] ?? null;
    const nextKey =
      learningSessionId && activeLessonId && (activeIsQuiz || slide)
        ? presentationContextKey({
            sessionId: learningSessionId,
            lessonId: activeLessonId,
            surface,
            slideId: slide?.id ?? null,
            slideIndex: currentSlide,
          })
        : null;

    if (presentationKeyRef.current === nextKey) return;
    presentationKeyRef.current = nextKey;

    // Buffer vẫn thuộc presentation cũ tại thời điểm này.
    flushPendingGaze();

    // Invalidate ngay: onFrame sẽ bỏ mọi frame cho tới khi presentation mới
    // được tạo và AOI snapshot mới sẵn sàng.
    activePresentationKeyRef.current = null;
    presentationIdRef.current = null;
    aoiSnapshotIdRef.current = null;
    aoiReadyRef.current = false;
    layoutGenerationRef.current = 0;
    setPresentationId(null);

    if (!nextKey || !learningSessionId) {
      presentationEntryRef.current = null;
      presentationRequestRef.current.invalidate();
      return;
    }

    // Mỗi lần vào slide (kể cả quay lại slide cũ sau khi đã rời đi) là một
    // content view mới. Cùng key thì giữ nguyên UUID để retry idempotent.
    const entry = presentationEntryFor(presentationEntryRef.current, nextKey);
    presentationEntryRef.current = entry;

    const token = presentationRequestRef.current.begin(nextKey);
    const sequenceNo = presentationSequenceRef.current;
    presentationSequenceRef.current += 1;
    createPresentation(learningSessionId, {
      slideId: slide?.id ?? null,
      surface,
      sequenceNo,
      clientPresentationId: entry.clientPresentationId,
      enteredAt: entry.enteredAt,
    })
      .then((presentation) => {
        if (!presentationRequestRef.current.isActive(token)) return;
        activePresentationKeyRef.current = nextKey;
        presentationIdRef.current = presentation.id;
        setPresentationId(presentation.id);
      })
      .catch(() => {
        if (!presentationRequestRef.current.isActive(token)) return;
        activePresentationKeyRef.current = null;
        presentationIdRef.current = null;
        setPresentationId(null);
      });
  }, [
    learningSessionId,
    activeLessonId,
    activeIsQuiz,
    currentSlide,
    slides,
    flushPendingGaze,
  ]);

  // Chặn response presentation đến sau khi component đã unmount.
  useEffect(
    () => () => {
      presentationRequestRef.current.invalidate();
      presentationEntryRef.current = null;
      activePresentationKeyRef.current = null;
      presentationIdRef.current = null;
      aoiReadyRef.current = false;
    },
    [],
  );

  // Đo layout DOM và tạo snapshot AOI. Tạm dừng ghi gaze trong lúc đo để
  // sample không bị gán sang layout mới.
  const aoiSnapshot = useAoiSnapshot({
    sessionId: learningSessionId ?? null,
    presentationId,
    enabled: Boolean(
      learningSessionId &&
        presentationId &&
        trackingAllowed &&
        !displayBlocked &&
        (total > 0 || activeIsQuiz),
    ),
    layoutKey,
    onBeforeSnapshot: pauseAndFlushGaze,
    requireImageTransform: !activeIsQuiz && total > 0,
  });

  useEffect(() => {
    if (
      !presentationId ||
      presentationIdRef.current !== presentationId ||
      aoiSnapshot.presentationId !== presentationId
    ) {
      aoiSnapshotIdRef.current = null;
      aoiReadyRef.current = false;
      layoutGenerationRef.current = 0;
      return;
    }
    aoiSnapshotIdRef.current = aoiSnapshot.snapshotId;
    aoiReadyRef.current = aoiSnapshot.ready;
    layoutGenerationRef.current = aoiSnapshot.layoutGeneration;
  }, [
    presentationId,
    aoiSnapshot.snapshotId,
    aoiSnapshot.presentationId,
    aoiSnapshot.ready,
    aoiSnapshot.layoutGeneration,
  ]);

  const enqueueGaze = useCallback(
    (sample: GazeSample) => {
      // Guard chặn cả ở tầng enqueue: kể cả một frame lọt qua trước khi
      // useGazeTracker kịp cleanup cũng không được ghi vào buffer.
      if (displayBlocked) return;
      if (gazeBufferLessonRef.current && gazeBufferLessonRef.current !== activeLessonId) {
        flushGazeForLesson(gazeBufferLessonRef.current);
      }
      if (!gazeBatchOwnerRef.current) {
        const presentationId = presentationIdRef.current;
        if (presentationId) {
          gazeBatchOwnerRef.current = {
            presentationId,
            layoutId: aoiSnapshotIdRef.current,
          };
        }
      }
      gazeBufferLessonRef.current = activeLessonId;
      gazeBufferRef.current.push(sample);
      if (gazeBufferRef.current.length >= GAZE_MAX_BATCH) {
        flushGaze();
      }
    },
    [activeLessonId, displayBlocked, flushGaze, flushGazeForLesson],
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
      activeLessonId &&
        trackingAllowed &&
        !displayBlocked &&
        (total > 0 || activeIsQuiz),
    ),
    calibrated: gazeCalibrated,
    allowSimulation: false,
    fps: gazeFps,
    getContext: () => ({
      // Chỉ gắn presentation/layout khi snapshot AOI đã sẵn sàng; frame gửi
      // trong lúc đo layout sẽ có presentationId=null và bị ingest bỏ.
      presentationId: aoiReadyRef.current ? presentationIdRef.current : null,
      layoutGeneration: aoiReadyRef.current ? layoutGenerationRef.current : 0,
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
        if (!learningSessionId || !trackingAllowed || displayBlocked) return;
        const activePresentationId = presentationIdRef.current;
        const activeKey = activePresentationKeyRef.current;
        if (!activePresentationId || !activeKey || !aoiReadyRef.current) return;

        const surface = activeIsQuiz ? "quiz" : "lesson";
        const slide = activeIsQuiz ? null : slides[currentSlide] ?? null;
        const expectedKey = presentationContextKey({
          sessionId: learningSessionId,
          lessonId: activeLessonId,
          surface,
          slideId: slide?.id ?? null,
          slideIndex: currentSlide,
        });
        // Context React hiện tại phải trùng presentation đã resolve; nếu
        // presentationId mới chưa về thì mọi frame đều bị bỏ.
        if (expectedKey !== activeKey) return;
        if (
          !isFrameForActiveContext(frame, {
            presentationId: activePresentationId,
            layoutGeneration: layoutGenerationRef.current,
            surface,
          })
        ) {
          return;
        }
        if (!isValidGazeSequence(frame.sequence)) return;
        // overloaded/stale không phải mẫu gaze; bỏ thay vì ghi dữ liệu rác.
        if (frame.status === "overloaded" || frame.status === "stale") return;

        const faceDetected = frame.status === "ok";
        if (faceDetected && (frame.x === null || frame.y === null)) return;
        enqueueGaze({
          sequence: frame.sequence,
          eventTime: frame.eventTime,
          // Toạ độ đã quy đổi sang viewport hiện tại; đây là nguồn duy nhất
          // cho mapping AOI.
          viewportX: faceDetected ? frame.currentX : null,
          viewportY: faceDetected ? frame.currentY : null,
          status: frame.status,
          qualityFlags: {},
        });
      },
      [
        learningSessionId,
        trackingAllowed,
        displayBlocked,
        enqueueGaze,
        activeLessonId,
        activeIsQuiz,
        currentSlide,
        slides,
      ],
    ),
  });

  // Điều hướng bàn phím
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      // Giữ phím không được tạo luồng đổi slide/presentation không kiểm soát.
      if (event.repeat) return;
      if (event.key === "ArrowRight") {
        setCurrentSlide((value) => getNextSlideIndex(value, total));
      }
      if (event.key === "ArrowLeft") {
        setCurrentSlide((value) => getPreviousSlideIndex(value));
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

  const selectLesson = useCallback(
    (lessonId: string) => {
      // Đóng phiên bài cũ trước khi chuyển
      if (activeLessonId !== lessonId) closeLearningSession(activeLessonId);
      setPendingCitation(null);
      setActiveLessonId(lessonId);
      setCurrentSlide(0);
    },
    [activeLessonId, closeLearningSession],
  );

  // Bấm citation: nhảy thẳng tới slide trong bài đang đọc thay vì mở dialog.
  // Trả false để chat mở dialog cho citation không phải slide (LMS, quiz...).
  const handleCitationNavigate = useCallback(
    (citation: ChatCitation): boolean => {
      if (!citation.lessonId) return false;
      const lesson = allItems.find((item) => item.id === citation.lessonId);
      if (!lesson || lesson.kind === "quiz") return false;

      if (citation.lessonId !== activeLessonId) {
        selectLesson(citation.lessonId);
        setPendingCitation(citation);
        return true;
      }

      const index = findCitationSlideIndex(citation, slides);
      if (index >= 0) {
        setCurrentSlide(index);
      } else {
        setPendingCitation(citation);
      }
      return true;
    },
    [activeLessonId, allItems, selectLesson, slides],
  );

  const goToPreviousSlide = useCallback(() => {
    setCurrentSlide((value) => getPreviousSlideIndex(value));
  }, []);

  const goToNextSlide = useCallback(() => {
    setCurrentSlide((value) => getNextSlideIndex(value, total));
  }, [total]);

  if (courseLoading) {
    return <ReaderLoading />;
  }

  if (courseError || !course) {
    return <ReaderError onRetry={() => refetch()} />;
  }

  return (
    <ReaderView
      courseId={courseId}
      courseTitle={course.title}
      modules={course.modules}
      activeLessonId={activeLessonId}
      activeLesson={activeLesson ?? null}
      activeModule={activeModule ?? null}
      slides={slides}
      currentSlide={currentSlide}
      activeIsQuiz={activeIsQuiz}
      quizId={activeQuizId}
      nextLesson={nextLesson}
      slidesLoading={slidesLoading}
      slidePdfUrl={slidePdfUrl}
      currentContent={currentContent}
      chatOpen={chatOpen}
      chatAllowed={chatAllowed}
      chatReason={
        chatAccess.data?.reason ??
        (chatAccess.isError ? "Không kiểm tra được quyền dùng chatbot" : null)
      }
      chatButtonRef={assistantButtonRef}
      onToggleChat={toggleChat}
      onCloseChat={closeChat}
      onSelectLesson={selectLesson}
      onPrevSlide={goToPreviousSlide}
      onNextSlide={goToNextSlide}
      onCitationNavigate={handleCitationNavigate}
      gazeSource={gazeSource}
      calibrationRequired={calibrationRequired}
      showGazeDot={showGazeDot}
      gazeDot={gazeDot}
      displayGuard={displayGuard}
    />
  );
}
