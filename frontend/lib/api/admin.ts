import { apiFetch } from "./client";

export interface AdminStudent {
  id: string;
  name: string;
  email: string;
  studentCode?: string | null;
  program?: string | null;
  avatarUrl?: string | null;
  createdAt: string;
}

interface PromoteStudentResult {
  ok: boolean;
  teacherCode: string;
}

export function fetchAdminStudents(q?: string): Promise<AdminStudent[]> {
  return apiFetch<AdminStudent[]>("/api/admin/students", { params: { q } });
}

export function promoteStudent(
  userId: string,
  payload: { teacherCode?: string | null; department?: string | null },
): Promise<PromoteStudentResult> {
  return apiFetch<PromoteStudentResult>(`/api/admin/students/${userId}/promote`, {
    method: "POST",
    body: payload,
  });
}
