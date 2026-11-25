"use client";

import { useMemo } from "react";
import { Icon } from "@/components/ui/icon";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import type { CourseVisitRow } from "@/lib/api/visits";
import type { SummaryScope, SummarySurface } from "@/lib/types/visualization";

interface StudentOption {
  id: string;
  name: string;
  code: string;
}

export function SummaryFilters({
  visits,
  lessons,
  scope,
  onScope,
  studentId,
  onStudent,
  selectedStudentIds,
  onSelectedStudents,
  visitId,
  onVisit,
  lessonId,
  onLesson,
  from,
  onFrom,
  to,
  onTo,
  surface,
  onSurface,
  includeDropped,
  onIncludeDropped,
  onlyCounted,
  onOnlyCounted,
  onReset,
}: {
  visits: CourseVisitRow[];
  lessons: { id: string; title: string }[];
  scope: SummaryScope;
  onScope: (scope: SummaryScope) => void;
  studentId: string;
  onStudent: (id: string) => void;
  selectedStudentIds: string[];
  onSelectedStudents: (ids: string[]) => void;
  visitId: string;
  onVisit: (id: string) => void;
  lessonId: string;
  onLesson: (id: string) => void;
  from: string;
  onFrom: (value: string) => void;
  to: string;
  onTo: (value: string) => void;
  surface: SummarySurface;
  onSurface: (value: SummarySurface) => void;
  includeDropped: boolean;
  onIncludeDropped: (value: boolean) => void;
  onlyCounted: boolean;
  onOnlyCounted: (value: boolean) => void;
  onReset: () => void;
}) {
  const students = useMemo(() => {
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
  }, [visits]);

  const resolvedStudent = students.some((student) => student.id === studentId)
    ? studentId
    : students[0]?.id ?? "";
  const studentVisits = visits.filter(
    (visit) => visit.studentId === resolvedStudent,
  );
  const resolvedVisit = studentVisits.some((visit) => visit.id === visitId)
    ? visitId
    : studentVisits[0]?.id ?? "";

  const toggleStudent = (id: string) => {
    onSelectedStudents(
      selectedStudentIds.includes(id)
        ? selectedStudentIds.filter((value) => value !== id)
        : [...selectedStudentIds, id],
    );
  };

  return (
    <div className="space-y-4 rounded-[20px] border border-border bg-card p-4 shadow-xs">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex flex-wrap rounded-full border border-border bg-muted/40 p-1">
          {(
            [
              ["visit", "Một ca · một sinh viên"],
              ["student", "Nhiều ca · một sinh viên"],
              ["cohort", "Nhiều ca · nhiều sinh viên"],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => onScope(key)}
              className={cn(
                "rounded-full px-3 py-1.5 text-xs font-semibold transition-colors",
                scope === key
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {label}
            </button>
          ))}
        </div>
        <span className="ml-auto text-xs text-muted-foreground">
          {scope === "cohort" && selectedStudentIds.length > 0
            ? `${selectedStudentIds.length} học viên được chọn`
            : `${students.length} học viên có dữ liệu`}
        </span>
      </div>

      {scope === "cohort" ? (
        <div className="rounded-[16px] border border-border bg-muted/40 p-2">
          <div className="flex items-center justify-between gap-2 px-2 py-1">
            <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
              Chọn học viên
            </p>
            <button
              type="button"
              onClick={() => onSelectedStudents([])}
              className="text-[11px] font-medium text-muted-foreground hover:text-foreground"
            >
              Tất cả
            </button>
          </div>
          <div className="grid max-h-40 gap-1 overflow-y-auto sm:grid-cols-2 lg:grid-cols-3">
            {students.map((student) => {
              const checked = selectedStudentIds.includes(student.id);
              return (
                <label
                  key={student.id}
                  className="flex items-center gap-2 rounded-xl px-2 py-1.5 text-xs text-muted-foreground hover:bg-card"
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleStudent(student.id)}
                    className="size-3.5 accent-[var(--primary)]"
                  />
                  <span className="min-w-0 flex-1 truncate">
                    {student.name}
                    {student.code ? ` · ${student.code}` : ""}
                  </span>
                </label>
              );
            })}
          </div>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
              Học viên
            </span>
            <select
              value={resolvedStudent}
              onChange={(event) => {
                onStudent(event.target.value);
                onVisit("");
              }}
              className="h-10 w-full rounded-2xl border border-border bg-muted/40 px-3 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
            >
              {students.map((student) => (
                <option key={student.id} value={student.id}>
                  {student.name}
                  {student.code ? ` · ${student.code}` : ""}
                </option>
              ))}
            </select>
          </label>
          {scope === "visit" && (
            <label className="block">
              <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
                Ca học
              </span>
              <select
                value={resolvedVisit}
                onChange={(event) => onVisit(event.target.value)}
                className="h-10 w-full rounded-2xl border border-border bg-muted/40 px-3 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
              >
                {studentVisits.map((visit) => (
                  <option key={visit.id} value={visit.id}>
                    {new Date(visit.startedAt).toLocaleString("vi-VN")} ·{" "}
                    {visit.lessonSessionCount} bài
                  </option>
                ))}
              </select>
            </label>
          )}
          {scope === "student" && (
            <div className="flex items-end pb-2 text-xs text-muted-foreground">
              Tính tất cả {studentVisits.length} ca của học viên này.
            </div>
          )}
        </div>
      )}

      <details className="group">
        <summary className="flex cursor-pointer list-none items-center gap-1.5 text-xs font-semibold text-muted-foreground hover:text-foreground">
          <Icon name="ri-settings-3-line" className="size-3.5" />
          Bộ lọc nâng cao
          <Icon
            name="ri-arrow-down-s-line"
            className="size-3.5 transition-transform group-open:rotate-180"
          />
        </summary>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className="block">
            <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
              Bài học
            </span>
            <select
              value={lessonId}
              onChange={(event) => onLesson(event.target.value)}
              className="h-10 w-full rounded-2xl border border-border bg-muted/40 px-3 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
            >
              <option value="">Tất cả bài</option>
              {lessons.map((lesson) => (
                <option key={lesson.id} value={lesson.id}>
                  {lesson.title}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
              Bề mặt
            </span>
            <select
              value={surface}
              onChange={(event) => onSurface(event.target.value as SummarySurface)}
              className="h-10 w-full rounded-2xl border border-border bg-muted/40 px-3 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
            >
              <option value="all">Tất cả</option>
              <option value="lesson">Bài giảng</option>
              <option value="quiz">Bài tập</option>
            </select>
          </label>
          <label className="block">
            <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
              Từ ngày
            </span>
            <input
              type="date"
              value={from}
              onChange={(event) => onFrom(event.target.value)}
              className="h-10 w-full rounded-2xl border border-border bg-muted/40 px-3 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
            />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
              Đến ngày
            </span>
            <input
              type="date"
              value={to}
              onChange={(event) => onTo(event.target.value)}
              className="h-10 w-full rounded-2xl border border-border bg-muted/40 px-3 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
            />
          </label>
        </div>
        <p className="mt-2 text-[11px] text-muted-foreground">
          Mặc định 90 ngày gần nhất. Xoá “Từ ngày” và “Đến ngày” để xem toàn bộ
          lịch sử.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <Switch
              checked={includeDropped}
              onCheckedChange={onIncludeDropped}
              ariaLabel="Bao gồm học viên đã gỡ"
            />
            Bao gồm học viên đã gỡ
          </label>
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <Switch
              checked={onlyCounted}
              onCheckedChange={onOnlyCounted}
              ariaLabel="Chỉ tính lượt >= ngưỡng"
            />
            {"Chỉ tính lượt >= ngưỡng"}
          </label>
          <button
            type="button"
            onClick={onReset}
            className="text-xs font-semibold text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
          >
            Xóa bộ lọc
          </button>
        </div>
      </details>
    </div>
  );
}
