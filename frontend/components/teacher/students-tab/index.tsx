"use client";

import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { useCourseStudents, useCourseTree, useStudentLessons } from "@/hooks/use-teacher";
import { removeCourseStudent } from "@/lib/api/teacher";
import type { StudentRow } from "@/lib/types/domain";
import {
  countStudentsByStatus,
  sortAndFilterStudents,
  type SortColumn,
  type SortState,
} from "../students-helpers";
import { AddStudentDialog } from "./add-student-dialog";
import { StudentDetailSheet } from "./student-detail-sheet";
import { StudentsSummary } from "./students-summary";
import { StudentsTable } from "./students-table";
import { StudentsToolbar } from "./students-toolbar";
import { queryKeys } from "@/lib/query-keys";

export function StudentsTab({ courseId, canManage }: { courseId: string; canManage: boolean }) {
  const queryClient = useQueryClient();
  const { data: students = [], isLoading, isError, error } = useCourseStudents(courseId);
  const { data: tree = [] } = useCourseTree(courseId);

  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortState>({ column: "lastActive", dir: "asc" });
  const [studentToRemove, setStudentToRemove] = useState<StudentRow | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const { data: studentLessons = [] } = useStudentLessons(courseId, openId ?? "");

  const rows = useMemo(
    () => sortAndFilterStudents(students, query, sort),
    [students, query, sort],
  );

  const toggleSort = (column: SortColumn) =>
    setSort((prev) =>
      prev.column === column
        ? { column, dir: prev.dir === "asc" ? "desc" : "asc" }
        : { column, dir: "asc" },
    );

  const counts = countStudentsByStatus(students);
  const hasActiveSearch = query.trim().length > 0;
  const openStudent = students.find((student) => student.id === openId) ?? null;
  const courseLessons = tree.flatMap((module) => module.lessons);
  const lessonTitle = (lessonId: string) =>
    courseLessons.find((lesson) => lesson.id === lessonId)?.title ?? lessonId;
  const openStudentLessons = openStudent
    ? courseLessons.map((lesson) => ({
        lessonId: lesson.id,
        attention: studentLessons.find((item) => item.lessonId === lesson.id)?.attention ?? null,
      }))
    : [];
  const removeStudent = async (id: string) => {
    try {
      await removeCourseStudent(courseId, id);
      queryClient.invalidateQueries({ queryKey: queryKeys.teacher.courseStudents(courseId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.teacher.coursesRoot });
    } catch {
      setAddError("Không gỡ được học viên khỏi khóa học");
    }
  };

  return (
    <div className="space-y-8">
      <StudentsSummary
        total={students.length}
        activeCount={counts.active}
        completedCount={counts.completed}
        canManage={canManage}
        onAdd={() => setShowAdd(true)}
      />

      {addError && (
        <div className="flex items-center gap-3 rounded-2xl border border-destructive/20 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <Icon name="ri-error-warning-line" className="size-4" />
          <span className="flex-1">{addError}</span>
          <button type="button" onClick={() => setAddError(null)} aria-label="Đóng" className="rounded-md p-1">
            <Icon name="ri-close-line" className="size-4" />
          </button>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-16 rounded-xl" />
          ))}
        </div>
      ) : isError ? (
        <EmptyState
          icon="ri-error-warning-line"
          title="Không tải được danh sách học viên"
          description={error instanceof Error ? error.message : "Vui lòng thử lại sau."}
        />
      ) : students.length === 0 ? (
        <EmptyState
          icon="ri-group-line"
          title="Chưa có học viên"
          description={
            canManage
              ? "Thêm học viên vào khóa học để bắt đầu."
              : "Bạn chưa có quyền quản lý danh sách học viên của khóa học này."
          }
          action={
            canManage ? (
              <Button className="rounded-full" onClick={() => setShowAdd(true)}>
                <Icon name="ri-user-add-line" className="size-4" />
                Thêm học viên
              </Button>
            ) : undefined
          }
        />
      ) : (
        <>
          <StudentsToolbar
            query={query}
            hasActiveSearch={hasActiveSearch}
            onQueryChange={setQuery}
            onClear={() => setQuery("")}
          />

          {rows.length === 0 ? (
            <EmptyState icon="ri-search-line" title="Không tìm thấy học viên phù hợp" description="Thử đổi từ khóa tìm kiếm." />
          ) : (
            <StudentsTable
              rows={rows}
              sort={sort}
              canManage={canManage}
              onSort={toggleSort}
              onOpen={(student) => setOpenId(student.id)}
              onRemove={setStudentToRemove}
            />
          )}
        </>
      )}

      <ConfirmDialog
        open={studentToRemove !== null}
        onOpenChange={(o) => !o && setStudentToRemove(null)}
        title={studentToRemove ? `Gỡ ${studentToRemove.name} khỏi khóa học?` : "Gỡ học viên?"}
        description="Học viên sẽ không còn trong danh sách đang học. Lịch sử học và dữ liệu đã ghi nhận vẫn được giữ lại."
        confirmLabel="Gỡ học viên"
        destructive
        onConfirm={() => {
          if (studentToRemove) void removeStudent(studentToRemove.id);
          setStudentToRemove(null);
        }}
      />

      <AddStudentDialog
        open={showAdd}
        onOpenChange={setShowAdd}
        courseId={courseId}
        enrolledIds={new Set(students.map((s) => s.id))}
        onAdded={() => {
          queryClient.invalidateQueries({ queryKey: queryKeys.teacher.courseStudents(courseId) });
          queryClient.invalidateQueries({ queryKey: queryKeys.teacher.coursesRoot });
        }}
        onError={setAddError}
      />

      <StudentDetailSheet
        student={openStudent}
        courseId={courseId}
        lessons={openStudentLessons}
        lessonTitle={lessonTitle}
        onOpenChange={(open) => !open && setOpenId(null)}
      />
    </div>
  );
}
