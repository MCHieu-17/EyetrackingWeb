"use client";

import { Badge } from "@/components/ui/badge";
import type { AoiSummaryAoi, AoiSummaryStudent } from "@/lib/types/visualization";
import { formatDuration } from "../replay/replay-geometry";
import { compositionForAois, topAois } from "./summary-helpers";

export function StudentCompareChart({
  students,
  byAoi,
}: {
  students: AoiSummaryStudent[];
  byAoi: AoiSummaryAoi[];
}) {
  const top = topAois(byAoi, 6).filter((item) => !item.isOther);
  if (students.length === 0) {
    return (
      <p className="px-4 py-10 text-center text-sm text-black/40">
        Chưa có dữ liệu học viên.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {students.slice(0, 12).map((student) => {
        const segments = compositionForAois(student.aois, student.durationMs, top);
        return (
          <div key={student.studentId}>
            <div className="mb-1 flex items-center gap-2">
              <span className="min-w-0 flex-1 truncate text-xs font-medium text-black/65">
                {student.studentName}
                {student.studentCode ? ` · ${student.studentCode}` : ""}
              </span>
              {student.enrollmentStatus === "dropped" && (
                <Badge variant="secondary" className="shrink-0">
                  Đã gỡ
                </Badge>
              )}
              <span className="shrink-0 text-[10px] tabular-nums text-black/40">
                {formatDuration(student.durationMs)}
              </span>
            </div>
            <div className="flex h-5 overflow-hidden rounded-full bg-[#f0f2ec]">
              {segments.map((segment) => (
                <span
                  key={segment.label}
                  className="h-full border-r border-white/40 last:border-0"
                  style={{
                    width: `${segment.percent}%`,
                    backgroundColor: segment.color,
                  }}
                  title={`${segment.name}: ${formatDuration(segment.durationMs)}`}
                />
              ))}
            </div>
          </div>
        );
      })}
      {students.length > 12 && (
        <p className="text-center text-[11px] text-black/40">
          Đang hiển thị 12/{students.length} học viên có thời lượng cao nhất.
        </p>
      )}
    </div>
  );
}
