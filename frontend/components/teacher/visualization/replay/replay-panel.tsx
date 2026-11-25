"use client";

import { useMemo, useState } from "react";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useCourseVisits, useVisitReplay } from "@/hooks/use-visualization";
import type { CourseVisitRow } from "@/lib/api/visits";
import { formatDateTime } from "./replay-geometry";
import { ReplayPlayer } from "./replay-player";

interface StudentOption {
  id: string;
  name: string;
  code: string;
}

function studentsOf(visits: CourseVisitRow[]): StudentOption[] {
  const map = new Map<string, StudentOption>();
  for (const visit of visits) {
    if (!map.has(visit.studentId)) {
      map.set(visit.studentId, {
        id: visit.studentId,
        name: visit.studentName,
        code: visit.studentCode,
      });
    }
  }
  return [...map.values()].sort((a, b) => a.name.localeCompare(b.name, "vi"));
}

function visitLabel(visit: CourseVisitRow): string {
  const ended = visit.endedAt ? "đã kết thúc" : "đang diễn ra";
  return `${formatDateTime(visit.startedAt)} · ${visit.lessonSessionCount} bài · ${visit.gazeCount} gaze · ${ended}`;
}

export function ReplayPanel({
  courseId,
  initialStudentId,
  initialVisitId,
}: {
  courseId: string;
  initialStudentId?: string | null;
  initialVisitId?: string | null;
}) {
  const { data: visits = [], isLoading, isError, refetch } = useCourseVisits(courseId, {
    limit: 1000,
  });
  const [studentId, setStudentId] = useState(initialStudentId ?? "");
  const [visitId, setVisitId] = useState(initialVisitId ?? "");

  const students = useMemo(() => studentsOf(visits), [visits]);
  // Deep link chỉ có visitId: suy ra học viên từ chính ca đó để không chọn
  // nhầm học viên đầu danh sách và rơi về ca khác.
  const initialVisitStudentId = useMemo(
    () => visits.find((visit) => visit.id === initialVisitId)?.studentId ?? "",
    [initialVisitId, visits],
  );
  const resolvedStudentId = students.some((student) => student.id === studentId)
    ? studentId
    : initialVisitStudentId &&
        students.some((student) => student.id === initialVisitStudentId)
      ? initialVisitStudentId
      : students[0]?.id ?? "";
  const studentVisits = useMemo(
    () => visits.filter((visit) => visit.studentId === resolvedStudentId),
    [resolvedStudentId, visits],
  );
  const resolvedVisitId = studentVisits.some((visit) => visit.id === visitId)
    ? visitId
    : studentVisits[0]?.id ?? "";

  const replay = useVisitReplay(resolvedVisitId || null);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-16 rounded-[18px]" />
        <Skeleton className="h-[420px] rounded-[20px]" />
      </div>
    );
  }

  if (isError) {
    return (
      <ErrorState
        title="Không tải được danh sách ca học"
        description="Vui lòng kiểm tra kết nối và thử lại."
        onRetry={() => void refetch()}
      />
    );
  }

  if (visits.length === 0) {
    return (
      <EmptyState
        icon="ri-focus-2-line"
        title="Chưa có ca học nào"
        description="Dữ liệu gaze sẽ xuất hiện sau khi học viên vào khóa học và bật theo dõi điểm nhìn."
      />
    );
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-3 rounded-[20px] border border-border bg-card p-4 shadow-xs sm:grid-cols-2 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.5fr)]">
        <label className="block">
          <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
            Học viên
          </span>
          <select
            value={resolvedStudentId}
            onChange={(event) => {
              setStudentId(event.target.value);
              setVisitId("");
            }}
            className="h-11 w-full rounded-2xl border border-border bg-muted/40 px-3 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
          >
            {students.map((student) => (
              <option key={student.id} value={student.id}>
                {student.name}
                {student.code ? ` · ${student.code}` : ""}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
            Ca học
          </span>
          <select
            value={resolvedVisitId}
            onChange={(event) => setVisitId(event.target.value)}
            className="h-11 w-full rounded-2xl border border-border bg-muted/40 px-3 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
          >
            {studentVisits.map((visit) => (
              <option key={visit.id} value={visit.id}>
                {visitLabel(visit)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {replay.isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-12 w-64 rounded-xl" />
          <div className="grid gap-4 lg:grid-cols-[250px_minmax(0,1fr)_310px]">
            <Skeleton className="h-[360px] rounded-[18px]" />
            <Skeleton className="h-[420px] rounded-[20px]" />
            <Skeleton className="h-[360px] rounded-[18px]" />
          </div>
        </div>
      ) : replay.isError || !replay.data ? (
        <ErrorState
          title="Không tải được ca học"
          description="Ca học có thể không còn dữ liệu hoặc bạn không có quyền xem."
          onRetry={() => void replay.refetch()}
        />
      ) : (
        <ReplayPlayer courseId={courseId} replay={replay.data} />
      )}
    </div>
  );
}
