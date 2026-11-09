"use client";

import * as React from "react";
import { Alert } from "@/components/ui/alert";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useAdminStudents } from "@/hooks/use-admin";
import type { AdminStudent } from "@/lib/api/admin";
import { initialsOf } from "@/lib/utils";
import { PromoteStudentDialog } from "./promote-student-dialog";

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date);
}

export function StudentPromotion() {
  const [query, setQuery] = React.useState("");
  const [selected, setSelected] = React.useState<AdminStudent | null>(null);
  const [notice, setNotice] = React.useState<string | null>(null);
  const {
    data: students = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useAdminStudents(query);

  return (
    <div className="space-y-5">
      <div className="rounded-[18px] border border-[#eeeee9] bg-white p-2 shadow-xs">
        <div className="relative">
          <Icon
            name="ri-search-line"
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Tìm theo tên, email hoặc mã sinh viên"
            className="h-10 rounded-full border-transparent bg-[#f5f6f2] pl-10 shadow-none focus-visible:border-border"
            aria-label="Tìm sinh viên"
          />
        </div>
      </div>

      {notice && <Alert variant="success" title={notice} />}

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, index) => (
            <Skeleton key={index} className="h-20 rounded-[18px]" />
          ))}
        </div>
      ) : isError ? (
        <ErrorState
          title="Không tải được danh sách sinh viên"
          description={error instanceof Error ? error.message : "Vui lòng thử lại."}
          onRetry={() => refetch()}
        />
      ) : students.length === 0 ? (
        <EmptyState
          icon="ri-user-line"
          title="Không có sinh viên phù hợp"
          description={
            query.trim()
              ? "Thử từ khóa khác."
              : "Chưa có tài khoản sinh viên nào đang hoạt động."
          }
        />
      ) : (
        <div className="space-y-2.5">
          <div className="flex items-center justify-between gap-4 px-1 py-1 sm:px-2">
            <h2 className="text-[10px] font-bold uppercase tracking-[0.15em] text-muted-foreground">
              Danh sách sinh viên
            </h2>
            <span className="rounded-full bg-muted px-2.5 py-1 font-mono text-[10px] font-semibold tabular-nums text-muted-foreground">
              {students.length}
            </span>
          </div>

          {students.map((student) => (
            <article
              key={student.id}
              className="flex flex-col gap-3 rounded-[18px] border border-[#eeeee9] bg-white p-4 shadow-xs sm:flex-row sm:items-center sm:gap-4 sm:px-5"
            >
              <Avatar className="size-11">
                {student.avatarUrl ? (
                  <AvatarImage src={student.avatarUrl} alt={student.name} />
                ) : null}
                <AvatarFallback>{initialsOf(student.name)}</AvatarFallback>
              </Avatar>

              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-foreground">
                  {student.name}
                </p>
                <p className="truncate text-xs text-muted-foreground">
                  {student.email}
                </p>
                <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <Badge variant="outline">
                    {student.studentCode || "Chưa có mã SV"}
                  </Badge>
                  {student.program ? (
                    <span className="truncate">{student.program}</span>
                  ) : null}
                  <span>· Tham gia {formatDate(student.createdAt)}</span>
                </div>
              </div>

              <Button
                type="button"
                className="w-full sm:w-auto"
                onClick={() => {
                  setNotice(null);
                  setSelected(student);
                }}
              >
                <Icon name="ri-user-follow-line" />
                Nâng cấp
              </Button>
            </article>
          ))}
        </div>
      )}

      <PromoteStudentDialog
        student={selected}
        open={selected !== null}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
        onPromoted={(message) => setNotice(message)}
      />
    </div>
  );
}
