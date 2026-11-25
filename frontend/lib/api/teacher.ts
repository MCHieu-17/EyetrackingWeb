import { apiFetch, apiFetchMultipart } from "./client";
import type {
  TeacherCourse,
  CourseStatus,
  LessonNode,
  ModuleItemRef,
  ModuleNode,
  StudentRow,
  SlideAdmin,
} from "@/lib/types/domain";

export interface CourseListQuery {
  status?: CourseStatus;
  q?: string;
}

export function fetchTeacherCourses(query: CourseListQuery = {}): Promise<TeacherCourse[]> {
  const { status, q } = query;
  return apiFetch<TeacherCourse[]>("/api/teacher/courses", {
    params: { status, q },
  });
}

export function fetchCourseTree(courseId: string): Promise<ModuleNode[]> {
  return apiFetch<ModuleNode[]>(`/api/teacher/courses/${courseId}`);
}

export function fetchCourseStudents(courseId: string): Promise<StudentRow[]> {
  return apiFetch<StudentRow[]>(`/api/teacher/courses/${courseId}/students`);
}

export function fetchStudentLessons(
  courseId: string,
  studentId: string,
): Promise<StudentRow["lessons"]> {
  return apiFetch<StudentRow["lessons"]>(
    `/api/teacher/courses/${courseId}/students/${studentId}/lessons`,
  );
}

interface StudentDirectoryEntry {
  id: string;
  name: string;
  code: string;
  email?: string;
  color: string;
}

export function fetchStudentDirectory(q?: string): Promise<StudentDirectoryEntry[]> {
  return apiFetch<StudentDirectoryEntry[]>(
    `/api/teacher/students${q?.trim() ? `?q=${encodeURIComponent(q.trim())}` : ""}`,
  );
}

export function addCourseStudents(
  courseId: string,
  studentIds: string[],
): Promise<{ ok: boolean; added: number }> {
  return apiFetch(`/api/teacher/courses/${courseId}/students`, {
    method: "POST",
    body: { studentIds },
  });
}

export function removeCourseStudent(
  courseId: string,
  studentId: string,
): Promise<{ ok: boolean }> {
  return apiFetch(`/api/teacher/courses/${courseId}/students/${studentId}`, {
    method: "DELETE",
  });
}

interface CourseWriteInput {
  title: string;
  description?: string;
  status?: CourseStatus;
  /** Cờ cấp khóa: cho sinh viên thấy chấm điểm nhìn (mọi bài giảng + bài tập). */
  showGazeDot?: boolean;
  /** Cờ cấp khóa: cho sinh viên thấy khung xem trước camera. */
  showCameraPreview?: boolean;
  /** Cờ cấp khóa: bắt buộc hiệu chỉnh trước khi vào học. */
  requireCalibration?: boolean;
}

export function createCourse(input: CourseWriteInput): Promise<TeacherCourse> {
  return apiFetch<TeacherCourse>("/api/teacher/courses", { method: "POST", body: input });
}

export function updateCourse(
  courseId: string,
  patch: Partial<CourseWriteInput>,
): Promise<TeacherCourse> {
  return apiFetch<TeacherCourse>(`/api/teacher/courses/${courseId}`, {
    method: "PATCH",
    body: patch,
  });
}

export function deleteCourse(courseId: string): Promise<{ ok: boolean }> {
  return apiFetch(`/api/teacher/courses/${courseId}`, { method: "DELETE" });
}

export function publishCourse(courseId: string): Promise<{ ok: boolean }> {
  return apiFetch(`/api/teacher/courses/${courseId}/publish`, {
    method: "POST",
  });
}

export function setCourseGazeDot(
  courseId: string,
  showGazeDot: boolean,
): Promise<{ ok: boolean; showGazeDot: boolean }> {
  return apiFetch(`/api/teacher/courses/${courseId}/gaze-dot`, {
    method: "PATCH",
    body: { showGazeDot },
  });
}

export function setCourseRequireCalibration(
  courseId: string,
  requireCalibration: boolean,
): Promise<{ ok: boolean; requireCalibration: boolean }> {
  return apiFetch(`/api/teacher/courses/${courseId}/require-calibration`, {
    method: "PATCH",
    body: { requireCalibration },
  });
}

export function setCourseCameraPreview(
  courseId: string,
  showCameraPreview: boolean,
): Promise<{ ok: boolean; showCameraPreview: boolean }> {
  return apiFetch(`/api/teacher/courses/${courseId}/camera-preview`, {
    method: "PATCH",
    body: { showCameraPreview },
  });
}

export function createModule(courseId: string, title: string): Promise<{ id: string }> {
  return apiFetch(`/api/teacher/courses/${courseId}/modules`, {
    method: "POST",
    body: { title },
  });
}

export function updateModule(moduleId: string, title: string): Promise<{ id: string }> {
  return apiFetch(`/api/teacher/modules/${moduleId}`, {
    method: "PATCH",
    body: { title },
  });
}

export function deleteModule(moduleId: string): Promise<{ ok: boolean }> {
  return apiFetch(`/api/teacher/modules/${moduleId}`, { method: "DELETE" });
}

export function createLesson(
  moduleId: string,
  title: string,
): Promise<{ id: string }> {
  return apiFetch(`/api/teacher/modules/${moduleId}/lessons`, {
    method: "POST",
    body: { title },
  });
}

export function createModuleQuizItem(
  moduleId: string,
  input: { title?: string; durationMinutes?: number; afterId?: string } = {},
): Promise<LessonNode> {
  return apiFetch<LessonNode>(`/api/teacher/modules/${moduleId}/quizzes`, {
    method: "POST",
    body: {
      title: input.title,
      durationMinutes: input.durationMinutes,
      afterId: input.afterId,
    },
  });
}

export function reorderModuleItems(
  moduleId: string,
  items: ModuleItemRef[],
): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>(`/api/teacher/modules/${moduleId}/items/reorder`, {
    method: "POST",
    body: { items },
  });
}

export function updateLesson(
  lessonId: string,
  patch: { title?: string },
): Promise<{ ok: boolean }> {
  return apiFetch(`/api/teacher/lessons/${lessonId}`, {
    method: "PATCH",
    body: patch,
  });
}

export function deleteLesson(lessonId: string): Promise<{ ok: boolean }> {
  return apiFetch(`/api/teacher/lessons/${lessonId}`, { method: "DELETE" });
}

export interface SlideImportJob {
  id: string;
  status: "queued" | "processing" | "ready" | "failed" | "cancelled";
  filename: string;
  pageCount: number | null;
  error: string | null;
  createdAt: string;
  finishedAt: string | null;
}

export function uploadLessonSlides(
  lessonId: string,
  file: File,
): Promise<{ ok: boolean; jobId: string; status: string }> {
  const form = new FormData();
  form.append("file", file, file.name);
  return apiFetchMultipart(`/api/teacher/lessons/${lessonId}/slides/upload`, form, "POST");
}

export function fetchSlideImportJob(
  lessonId: string,
  jobId: string,
): Promise<SlideImportJob> {
  return apiFetch<SlideImportJob>(
    `/api/teacher/lessons/${lessonId}/slides/imports/${jobId}`,
  );
}

export function fetchLessonSlidesAdmin(
  lessonId: string,
): Promise<SlideAdmin[]> {
  return apiFetch<SlideAdmin[]>(`/api/teacher/lessons/${lessonId}/slides`);
}

export function reindexLessonSlides(
  lessonId: string,
): Promise<{ ok: boolean; queued: number }> {
  return apiFetch(`/api/teacher/lessons/${lessonId}/slides/reindex`, {
    method: "POST",
  });
}

