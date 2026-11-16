"use client";

import type { AoiSummaryAoi, AoiSummaryLesson } from "@/lib/types/visualization";
import { formatDuration } from "../replay/replay-geometry";
import { aoiColor, compositionForLesson, topAois } from "./summary-helpers";

export function AoiCompositionChart({
  lessons,
  byAoi,
}: {
  lessons: AoiSummaryLesson[];
  byAoi: AoiSummaryAoi[];
}) {
  const top = topAois(byAoi, 6).filter((item) => !item.isOther);
  if (lessons.length === 0) {
    return (
      <p className="px-4 py-10 text-center text-sm text-black/40">
        Chưa có dữ liệu theo bài học.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-x-4 gap-y-1.5">
        {top.map((item) => (
          <span
            key={item.label}
            className="inline-flex items-center gap-1.5 text-[10px] text-black/50"
          >
            <span
              className="size-2 rounded-full"
              style={{ backgroundColor: aoiColor(item) }}
            />
            <span className="max-w-32 truncate">{item.name}</span>
          </span>
        ))}
        <span className="inline-flex items-center gap-1.5 text-[10px] text-black/50">
          <span className="size-2 rounded-full bg-[#9ca3af]" />
          Khác
        </span>
      </div>
      <div className="space-y-3">
        {lessons.map((lesson) => {
          const segments = compositionForLesson(lesson, top);
          return (
            <div key={lesson.lessonId}>
              <div className="mb-1 flex items-center justify-between gap-2">
                <span className="truncate text-xs font-medium text-black/65">
                  {lesson.lessonTitle}
                </span>
                <span className="shrink-0 text-[10px] tabular-nums text-black/40">
                  {formatDuration(lesson.durationMs)}
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
      </div>
    </div>
  );
}
