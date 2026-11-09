"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useCourseTree, useLessonSlidesAdmin } from "@/hooks/use-teacher";
import {
  fetchAoiSets,
  generateSlideAois,
  generateUiAois,
  rebuildAoiHits,
  saveSlideAois,
  saveUiAois,
  type AoiDefinitionInput,
} from "@/lib/api/aoi";
import {
  countCustom,
  nextCustomCode,
  nextUiCustomCode,
  pickLatest,
  toInputs,
} from "@/lib/aoi/editor-helpers";
import {
  UI_COMPONENTS,
  UI_SCHEMA_VERSION,
  friendlyUiName,
} from "@/lib/aoi/ui-components";
import type { LessonItem, ModuleItem } from "@/lib/types/domain";
import { useAoiAutosave } from "./use-aoi-autosave";

type AoiEditorMode = "edit" | "interact";
type AoiEditorTab = "slide" | "ui";

export function useAoiEditor({
  courseId,
  canManage,
}: {
  courseId: string;
  canManage: boolean;
}) {
  const queryClient = useQueryClient();
  const router = useRouter();
  const searchParams = useSearchParams();

  const {
    data: tree = [],
    isLoading: treeLoading,
    isError: treeError,
    refetch: refetchTree,
  } = useCourseTree(courseId);

  const lessons = useMemo(
    () => tree.flatMap((module) => module.lessons),
    [tree],
  );
  const firstLesson =
    lessons.find((lesson) => lesson.kind === "lesson" && lesson.slides > 0) ??
    lessons[0] ??
    null;

  const [activeLessonId, setActiveLessonId] = useState(
    () => searchParams.get("lesson") ?? "",
  );
  const resolvedLessonId = lessons.some((item) => item.id === activeLessonId)
    ? activeLessonId
    : firstLesson?.id ?? "";
  if (resolvedLessonId !== activeLessonId) {
    setActiveLessonId(resolvedLessonId);
  }

  const activeLesson =
    lessons.find((item) => item.id === resolvedLessonId) ?? null;
  const activeModule =
    tree.find((module) =>
      module.lessons.some((item) => item.id === resolvedLessonId),
    ) ?? null;
  const activeIsQuiz = activeLesson?.kind === "quiz";

  const {
    data: slides = [],
    isLoading: slidesLoading,
    isError: slidesError,
    refetch: refetchSlides,
  } = useLessonSlidesAdmin(activeIsQuiz ? "" : resolvedLessonId);

  const [activeSlideId, setActiveSlideId] = useState(
    () => searchParams.get("slide") ?? "",
  );
  const resolvedSlideId = slides.some((item) => item.id === activeSlideId)
    ? activeSlideId
    : slides[0]?.id ?? "";
  if (resolvedSlideId !== activeSlideId) {
    setActiveSlideId(resolvedSlideId);
  }

  const activeSlide =
    slides.find((item) => item.id === resolvedSlideId) ?? null;
  const currentSlideIndex = Math.max(
    0,
    slides.findIndex((item) => item.id === resolvedSlideId),
  );
  const slideVersionId = activeSlide?.slideVersionId ?? null;

  const [mode, setModeState] = useState<AoiEditorMode>("edit");
  const [tab, setTabState] = useState<AoiEditorTab>("slide");
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const [showOverlays, setShowOverlays] = useState(true);

  if (activeIsQuiz && tab === "slide") {
    setTabState("ui");
  }

  const slideSetQuery = useQuery({
    queryKey: ["aoi-sets", "slide", slideVersionId],
    queryFn: () =>
      fetchAoiSets({ scope: "slide", slideVersionId: slideVersionId! }),
    enabled: Boolean(slideVersionId),
  });
  const uiSetQuery = useQuery({
    queryKey: ["aoi-sets", "ui", UI_SCHEMA_VERSION],
    queryFn: () =>
      fetchAoiSets({ scope: "ui", uiSchemaVersion: UI_SCHEMA_VERSION }),
  });

  const slideSet = useMemo(
    () => pickLatest(slideSetQuery.data),
    [slideSetQuery.data],
  );
  const uiSet = useMemo(() => pickLatest(uiSetQuery.data), [uiSetQuery.data]);

  const [slideDefinitions, setSlideDefinitions] = useState<AoiDefinitionInput[]>(
    [],
  );
  const [uiDefinitions, setUiDefinitions] = useState<AoiDefinitionInput[]>([]);
  const [slideReady, setSlideReady] = useState(false);
  const [uiReady, setUiReady] = useState(false);
  const [syncedSlideSetId, setSyncedSlideSetId] = useState<string | null>(null);
  const [syncedUiSetId, setSyncedUiSetId] = useState<string | null>(null);
  const [slideRevision, setSlideRevision] = useState<number | undefined>(
    undefined,
  );
  const [uiRevision, setUiRevision] = useState<number | undefined>(undefined);

  const generatedSlideRef = useRef<string | null>(null);
  const generatedUiRef = useRef<string | null>(null);
  const rebuildTimerRef = useRef(0);

  // Render-phase adjust: đồng bộ dữ liệu server vào state cục bộ khi đổi bộ
  // vùng. Không dùng effect để tránh setState trong effect.
  if (slideSet && syncedSlideSetId !== slideSet.id) {
    setSlideRevision(slideSet.revision);
    setSyncedSlideSetId(slideSet.id);
    setSlideDefinitions(toInputs(slideSet.definitions));
    setSlideReady(true);
  } else if (!slideSet && syncedSlideSetId !== null) {
    setSyncedSlideSetId(null);
    setSlideRevision(undefined);
    setSlideDefinitions([]);
    setSlideReady(false);
  }

  if (uiSet && syncedUiSetId !== uiSet.id) {
    setUiRevision(uiSet.revision);
    setSyncedUiSetId(uiSet.id);
    setUiDefinitions(toInputs(uiSet.definitions));
    setUiReady(true);
  } else if (!uiSet && syncedUiSetId !== null) {
    setSyncedUiSetId(null);
    setUiRevision(undefined);
    setUiDefinitions([]);
    setUiReady(false);
  }

  const scheduleRebuild = useCallback(() => {
    if (!activeLessonId) return;
    window.clearTimeout(rebuildTimerRef.current);
    rebuildTimerRef.current = window.setTimeout(() => {
      void rebuildAoiHits({ courseId, lessonId: activeLessonId }).catch(() => {});
    }, 5000);
  }, [courseId, activeLessonId]);

  const generateSlideMutation = useMutation({
    mutationFn: ({
      slideVersionId: versionId,
      slideNumber,
      replaceAuto,
      resetAll,
    }: {
      slideVersionId: string;
      slideNumber: number;
      replaceAuto?: boolean;
      resetAll?: boolean;
    }) =>
      generateSlideAois(versionId, {
        slideNumber,
        replaceAuto,
        resetAll,
      }),
    onSuccess: (saved) => {
      queryClient.setQueryData(
        ["aoi-sets", "slide", saved.slideVersionId],
        [saved],
      );
      scheduleRebuild();
    },
  });

  const generateUiMutation = useMutation({
    mutationFn: () =>
      generateUiAois(
        UI_SCHEMA_VERSION,
        UI_COMPONENTS.map(({ code, name }) => ({ code, name })),
        true,
      ),
    onSuccess: (saved) => {
      queryClient.setQueryData(
        ["aoi-sets", "ui", UI_SCHEMA_VERSION],
        [saved],
      );
      scheduleRebuild();
    },
  });

  useEffect(() => {
    if (!canManage || !slideVersionId || slideSet || slideSetQuery.isLoading) {
      return;
    }
    if (generatedSlideRef.current === slideVersionId) return;
    generatedSlideRef.current = slideVersionId;
    generateSlideMutation.mutate({
      slideVersionId,
      slideNumber: currentSlideIndex + 1,
    });
  }, [
    canManage,
    slideVersionId,
    slideSet,
    slideSetQuery.isLoading,
    currentSlideIndex,
    generateSlideMutation,
  ]);

  useEffect(() => {
    if (!canManage || tab !== "ui" || uiSet || uiSetQuery.isLoading) return;
    if (generatedUiRef.current === UI_SCHEMA_VERSION) return;
    generatedUiRef.current = UI_SCHEMA_VERSION;
    generateUiMutation.mutate();
  }, [
    canManage,
    tab,
    uiSet,
    uiSetQuery.isLoading,
    generateUiMutation,
  ]);

  const slideSave = useAoiAutosave({
    value: slideDefinitions,
    ready: slideReady,
    enabled: canManage && Boolean(slideVersionId),
    save: async (definitions) => {
      if (!slideVersionId) return;
      const saved = await saveSlideAois(slideVersionId, {
        definitions,
        expectedRevision: slideRevision,
      });
      setSlideRevision(saved.revision);
      setSyncedSlideSetId(saved.id);
      queryClient.setQueryData(
        ["aoi-sets", "slide", slideVersionId],
        [saved],
      );
      scheduleRebuild();
    },
  });

  const uiSave = useAoiAutosave({
    value: uiDefinitions,
    ready: uiReady,
    enabled: canManage,
    save: async (definitions) => {
      const saved = await saveUiAois(UI_SCHEMA_VERSION, {
        definitions,
        expectedRevision: uiRevision,
      });
      setUiRevision(saved.revision);
      setSyncedUiSetId(saved.id);
      queryClient.setQueryData(
        ["aoi-sets", "ui", UI_SCHEMA_VERSION],
        [saved],
      );
      scheduleRebuild();
    },
  });

  const flushSlide = slideSave.flush;
  const flushUi = uiSave.flush;

  useEffect(() => {
    return () => {
      window.clearTimeout(rebuildTimerRef.current);
      void flushSlide();
      void flushUi();
    };
  }, [flushSlide, flushUi]);

  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => {
      if (slideSave.status === "saving" || uiSave.status === "saving") {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [slideSave.status, uiSave.status]);

  useEffect(() => {
    const params = new URLSearchParams(searchParams.toString());
    if (activeLessonId) params.set("lesson", activeLessonId);
    else params.delete("lesson");
    if (activeSlideId) params.set("slide", activeSlideId);
    else params.delete("slide");
    const next = params.toString();
    if (next !== searchParams.toString()) {
      router.replace(`/teacher/courses/${courseId}?${next}`, {
        scroll: false,
      });
    }
  }, [activeLessonId, activeSlideId, courseId, router, searchParams]);

  const selectLesson = useCallback(
    (lessonId: string) => {
      void slideSave.flush();
      void uiSave.flush();
      setActiveLessonId(lessonId);
      setActiveSlideId("");
      setSelectedCode(null);
      const lesson = lessons.find((item) => item.id === lessonId);
      setTabState(lesson?.kind === "quiz" ? "ui" : "slide");
    },
    [lessons, slideSave, uiSave],
  );

  const selectSlide = useCallback(
    (slideId: string) => {
      void slideSave.flush();
      setActiveSlideId(slideId);
      setSelectedCode(null);
    },
    [slideSave],
  );

  const prevSlide = useCallback(() => {
    if (currentSlideIndex > 0) {
      selectSlide(slides[currentSlideIndex - 1].id);
    }
  }, [currentSlideIndex, selectSlide, slides]);

  const nextSlide = useCallback(() => {
    if (currentSlideIndex < slides.length - 1) {
      selectSlide(slides[currentSlideIndex + 1].id);
    }
  }, [currentSlideIndex, selectSlide, slides]);

  const createSlideAoi = useCallback(
    (rect: { xMin: number; yMin: number; xMax: number; yMax: number }) => {
      if (!canManage) return;
      const rootCode = `slide_${currentSlideIndex + 1}`;
      const hasRoot = slideDefinitions.some((item) => item.code === rootCode);
      const base = hasRoot
        ? slideDefinitions
        : [
            ...slideDefinitions,
            {
              code: rootCode,
              name: `Slide ${currentSlideIndex + 1}`,
              parentId: null,
              geometry: { xMin: 0, yMin: 0, xMax: 1, yMax: 1 },
              isContainer: true,
              kind: "system" as const,
              isActive: true,
            },
          ];
      const code = nextCustomCode(base, rootCode);
      const next: AoiDefinitionInput = {
        code,
        name: `Vùng ${countCustom(base) + 1}`,
        parentId: rootCode,
        geometry: rect,
        isContainer: false,
        kind: "custom",
        isActive: true,
      };
      setSlideDefinitions([...base, next]);
      setSelectedCode(code);
      setTabState("slide");
    },
    [canManage, currentSlideIndex, slideDefinitions],
  );

  const createUiComponentAoi = useCallback(
    (code: string) => {
      if (!canManage) return;
      const existing = uiDefinitions.find((item) => item.code === code);
      if (existing) {
        setSelectedCode(code);
        setTabState("ui");
        return;
      }
      const next: AoiDefinitionInput = {
        code,
        name: friendlyUiName(code),
        parentId: null,
        geometry: { selector: `[data-aoi='${code}']` },
        isContainer: false,
        kind: "ui",
        isActive: true,
      };
      setUiDefinitions((prev) => [...prev, next]);
      setSelectedCode(code);
      setTabState("ui");
    },
    [canManage, uiDefinitions],
  );

  const createUiCustomAoi = useCallback(
    (
      anchor: string,
      rect: { xMin: number; yMin: number; xMax: number; yMax: number },
    ) => {
      if (!canManage) return;
      const code = nextUiCustomCode(uiDefinitions);
      const next: AoiDefinitionInput = {
        code,
        name: `Vùng ${countCustom(uiDefinitions) + 1}`,
        parentId: null,
        geometry: { anchor, ...rect },
        isContainer: false,
        kind: "custom",
        isActive: true,
      };
      setUiDefinitions((prev) => [...prev, next]);
      setSelectedCode(code);
      setTabState("ui");
    },
    [canManage, uiDefinitions],
  );

  const renameAoi = useCallback(
    (code: string, name: string) => {
      if (!canManage) return;
      const clean = name.trim();
      if (!clean) return;
      if (tab === "slide") {
        setSlideDefinitions((prev) =>
          prev.map((item) =>
            item.code === code ? { ...item, name: clean } : item,
          ),
        );
      } else {
        setUiDefinitions((prev) =>
          prev.map((item) =>
            item.code === code ? { ...item, name: clean } : item,
          ),
        );
      }
    },
    [canManage, tab],
  );

  // Bỏ đánh dấu: giữ vùng lại (để bật lại) nhưng không tham gia phân tích.
  const deactivateAoi = useCallback(
    (code: string) => {
      if (!canManage || code === "no_label") return;
      const target = slideDefinitions.find((item) => item.code === code);
      if (!target || target.isContainer) return;
      setSlideDefinitions((prev) =>
        prev.map((item) =>
          item.code === code ? { ...item, isActive: false } : item,
        ),
      );
    },
    [canManage, slideDefinitions],
  );

  const restoreAoi = useCallback(
    (code: string) => {
      if (!canManage) return;
      setSlideDefinitions((prev) =>
        prev.map((item) =>
          item.code === code ? { ...item, isActive: true } : item,
        ),
      );
    },
    [canManage],
  );

  // Xóa hẳn chỉ dùng cho vùng giao diện; vùng slide luôn được bỏ đánh dấu.
  const deleteAoi = useCallback(
    (code: string) => {
      if (!canManage || code === "no_label") return;
      setUiDefinitions((prev) => prev.filter((item) => item.code !== code));
      if (selectedCode === code) setSelectedCode(null);
    },
    [canManage, selectedCode],
  );

  const changeMode = useCallback(
    (next: AoiEditorMode) => {
      if (next === "interact") {
        void slideSave.flush();
        void uiSave.flush();
      }
      setModeState(next);
    },
    [slideSave, uiSave],
  );

  const changeTab = useCallback((next: AoiEditorTab) => {
    setTabState(next);
    setSelectedCode(null);
  }, []);

  const retryGenerateSlide = useCallback(() => {
    if (!slideVersionId) return;
    generatedSlideRef.current = null;
    generateSlideMutation.mutate({
      slideVersionId,
      slideNumber: currentSlideIndex + 1,
    });
  }, [currentSlideIndex, generateSlideMutation, slideVersionId]);

  const regenerateSlide = useCallback(
    (mode: "auto" | "all") => {
      if (!slideVersionId) return;
      generatedSlideRef.current = slideVersionId;
      generateSlideMutation.mutate({
        slideVersionId,
        slideNumber: currentSlideIndex + 1,
        replaceAuto: mode === "auto",
        resetAll: mode === "all",
      });
    },
    [currentSlideIndex, generateSlideMutation, slideVersionId],
  );

  const retryGenerateUi = useCallback(() => {
    generatedUiRef.current = null;
    generateUiMutation.mutate();
  }, [generateUiMutation]);

  const frameModules: ModuleItem[] = useMemo(
    () =>
      tree.map((module, index) => ({
        id: module.id,
        orderIndex: index + 1,
        title: module.title,
        lessons: module.lessons.map((lesson) => ({
          id: lesson.id,
          title: lesson.title,
          kind: lesson.kind,
          slideCount: lesson.slides,
          quizId: lesson.quizId,
          quizStatus: lesson.quizStatus,
          questionCount: lesson.questionCount,
          durationMinutes: lesson.durationMinutes,
          dueAt: lesson.dueAt,
        })),
      })),
    [tree],
  );

  const frameActiveLesson: LessonItem | null = useMemo(() => {
    if (!activeLesson) return null;
    return (
      frameModules
        .flatMap((module) => module.lessons)
        .find((lesson) => lesson.id === activeLesson.id) ?? null
    );
  }, [activeLesson, frameModules]);

  const frameActiveModule =
    frameModules.find((module) =>
      module.lessons.some((lesson) => lesson.id === activeLessonId),
    ) ?? null;

  const activeSave = tab === "slide" ? slideSave : uiSave;

  return {
    tree,
    treeLoading,
    treeError,
    refetchTree,
    lessons,
    activeLesson,
    activeModule,
    activeLessonId,
    activeIsQuiz,
    slides,
    slidesLoading,
    slidesError,
    refetchSlides,
    activeSlide,
    activeSlideId,
    currentSlideIndex,
    slideVersionId,
    frameModules,
    frameActiveLesson,
    frameActiveModule,
    slideSet,
    uiSet,
    slideDefinitions,
    uiDefinitions,
    slideReady,
    uiReady,
    slideSave,
    uiSave,
    activeSave,
    mode,
    tab,
    selectedCode,
    showOverlays,
    canManage,
    setSelectedCode,
    setShowOverlays,
    changeMode,
    changeTab,
    selectLesson,
    selectSlide,
    prevSlide,
    nextSlide,
    createSlideAoi,
    createUiComponentAoi,
    createUiCustomAoi,
    renameAoi,
    deactivateAoi,
    restoreAoi,
    deleteAoi,
    retryGenerateSlide,
    regenerateSlide,
    retryGenerateUi,
    generatingSlide: generateSlideMutation.isPending,
    generatingUi: generateUiMutation.isPending,
    generateSlideError: generateSlideMutation.error,
    generateUiError: generateUiMutation.error,
  };
}

export type AoiEditorController = ReturnType<typeof useAoiEditor>;
