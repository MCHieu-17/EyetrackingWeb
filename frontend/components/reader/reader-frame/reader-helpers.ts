import type { LessonItem, ModuleItem } from "@/lib/types/domain";

export type GazeStatus = "active" | "off" | "disconnected";

export function allLessons(modules: ModuleItem[]): LessonItem[] {
  return modules.flatMap((module) => module.lessons);
}

export function getNextLesson(
  lessons: readonly LessonItem[],
  activeLessonId: string,
): LessonItem | undefined {
  const index = lessons.findIndex((lesson) => lesson.id === activeLessonId);
  return lessons[index + 1];
}

export function isAtLastSlide(currentSlide: number, total: number): boolean {
  return currentSlide === total - 1 && total > 0;
}

export function getGazeStatus(
  gazeSource: "real" | "off" | "simulated" | null,
  calibrationRequired: boolean,
): GazeStatus {
  if (gazeSource === "real") return "active";
  if (!calibrationRequired) return "off";
  return "disconnected";
}
