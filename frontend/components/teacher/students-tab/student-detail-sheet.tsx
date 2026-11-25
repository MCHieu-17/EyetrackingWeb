"use client";

import Link from "next/link";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { useStudentVisits } from "@/hooks/use-teacher";
import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { ENROLL_LABEL } from "@/lib/constants";
import { initialsOf } from "@/lib/utils";
import type { StudentRow } from "@/lib/types/domain";

/** Sheet chi tiết học viên: thông tin nhanh và mức quan sát theo từng bài. */
export function StudentDetailSheet({
  student,
  courseId,
  lessons,
  lessonTitle,
  onOpenChange,
}: {
  student: StudentRow | null;
  courseId: string;
  lessons: { lessonId: string; attention: number | null }[];
  lessonTitle: (lessonId: string) => string;
  onOpenChange: (open: boolean) => void;
}) {
  const { data: visits = [], isLoading: visitsLoading } = useStudentVisits(
    courseId,
    student?.id ?? "",
  );
  const dateLabel = (value: string | null) =>
    value ? new Date(value).toLocaleString("vi-VN") : "—";

  return (
    <Sheet open={student !== null} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="overflow-hidden">
        {student && (
          <>
            <SheetHeader className="border-b border-border p-6 pr-12">
              <div className="flex items-center gap-3">
                <Avatar className="size-11">
                  {student.avatarUrl ? <AvatarImage src={student.avatarUrl} alt={student.name} /> : null}
                  <AvatarFallback>{initialsOf(student.name)}</AvatarFallback>
                </Avatar>
                <div className="min-w-0">
                  <SheetTitle className="truncate">{student.name}</SheetTitle>
                  <SheetDescription>{student.code} · {student.lastActive || "—"}</SheetDescription>
                </div>
              </div>
              <div className="mt-4 grid grid-cols-2 divide-x divide-border rounded-2xl bg-accent py-3">
                <div className="px-2 text-center"><p className="text-[10px] text-muted-foreground">Quan sát</p><p className="mt-1 font-display text-sm font-semibold">{student.attention === null ? "—" : `${student.attention}%`}</p></div>
                <div className="px-2 text-center"><p className="text-[10px] text-muted-foreground">Trạng thái</p><p className="mt-1 truncate text-sm font-semibold">{student.status === "dropped" ? "Đã gỡ" : ENROLL_LABEL[student.status]}</p></div>
              </div>
            </SheetHeader>
            <SheetBody className="p-5">
              <div className="mb-4">
                <h3 className="text-sm font-semibold text-foreground">Bài học</h3>
                <p className="mt-1 text-xs text-muted-foreground">Mức độ quan sát của học viên theo từng bài.</p>
              </div>
              {lessons.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">Khóa học chưa có bài học.</div>
              ) : (
                <ul className="space-y-2">
                  {lessons.map((lesson) => {
                    return (
                      <li key={lesson.lessonId}>
                        <div className="block rounded-2xl border border-border bg-card p-4 shadow-sm">
                          <div className="flex items-start justify-between gap-3">
                            <p className="min-w-0 truncate text-sm font-medium text-foreground">{lessonTitle(lesson.lessonId)}</p>
                            <span className="shrink-0 text-xs text-muted-foreground">
                              Quan sát {lesson.attention === null ? "—" : `${lesson.attention}%`}
                            </span>
                          </div>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}

              <div className="mt-8 mb-4 flex items-end justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold text-foreground">Ca học</h3>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Mỗi lần vào khóa là một ca, gồm nhiều bài học.
                  </p>
                </div>
                <span className="text-xs text-muted-foreground">{visits.length} ca</span>
              </div>
              {visitsLoading ? (
                <div className="space-y-2">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <div key={i} className="h-16 animate-pulse rounded-2xl bg-muted" />
                  ))}
                </div>
              ) : visits.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
                  Chưa có ca học nào.
                </div>
              ) : (
                <ul className="space-y-2">
                  {visits.map((visit) => (
                    <li
                      key={visit.id}
                      className="rounded-2xl border border-border bg-card p-4 shadow-sm"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-foreground">
                            {dateLabel(visit.startedAt)}
                          </p>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {visit.endedAt
                              ? `Kết thúc ${dateLabel(visit.endedAt)}`
                              : "Đang diễn ra"}
                          </p>
                        </div>
                        <div className="shrink-0 text-right text-xs text-muted-foreground">
                          <p>{visit.lessonSessionCount} bài</p>
                          <p>{visit.gazeCount} gaze</p>
                        </div>
                      </div>
                      <Button
                        asChild
                        size="xs"
                        variant="outline"
                        className="mt-3 rounded-full"
                      >
                        <Link
                          href={`/teacher/courses/${courseId}?tab=visualization&mode=replay&studentId=${student.id}&visitId=${visit.id}`}
                        >
                          Xem lại ca học
                        </Link>
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </SheetBody>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
