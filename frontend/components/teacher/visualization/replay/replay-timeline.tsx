"use client";

import type { ReactNode } from "react";
import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/utils";
import type { ReplayView } from "@/lib/types/visualization";
import {
  formatDwellThreshold,
  formatDuration,
  viewDwellMs,
} from "./replay-geometry";

interface LessonGroup {
  lessonId: string;
  title: string;
  items: { view: ReplayView; index: number }[];
}

function groupByLesson(views: ReplayView[]): LessonGroup[] {
  const groups: LessonGroup[] = [];
  views.forEach((view, index) => {
    const last = groups.at(-1);
    if (last && last.lessonId === view.lessonId) {
      last.items.push({ view, index });
    } else {
      groups.push({
        lessonId: view.lessonId,
        title: view.lessonTitle,
        items: [{ view, index }],
      });
    }
  });
  return groups;
}

function repeatKey(view: ReplayView): string {
  return view.surface === "quiz"
    ? view.contentViewId
    : view.slideId ?? view.contentViewId;
}

/**
 * Đếm số lần xuất hiện của cùng một slide (hoặc cùng content view với quiz)
 * trên toàn bộ ca, để lượt xem lại hiện "Lần 2", "Lần 3"…
 */
function repeatOccurrences(views: ReplayView[]): Map<string, number> {
  const counts = new Map<string, number>();
  const occurrences = new Map<string, number>();
  for (const view of views) {
    const key = repeatKey(view);
    const next = (counts.get(key) ?? 0) + 1;
    counts.set(key, next);
    if (!occurrences.has(view.contentViewId)) {
      occurrences.set(view.contentViewId, next);
    }
  }
  return occurrences;
}

function TimelineBadge({
  children,
  tone,
}: {
  children: ReactNode;
  tone: "warning" | "muted" | "danger";
}) {
  return (
    <span
      className={cn(
        "rounded-full px-1.5 py-0.5 text-[9px] font-semibold leading-none",
        tone === "warning" && "bg-[#fbf5e7] text-[#8a6420]",
        tone === "muted" && "bg-[#f2f4ee] text-black/45",
        tone === "danger" && "bg-[#fdf1ec] text-[#8a3b27]",
      )}
    >
      {children}
    </span>
  );
}

export function ReplayTimeline({
  views,
  currentIndex,
  onSelect,
  allViews = views,
  shortViewCount = 0,
  filtered = false,
  minDwellMs = 1000,
}: {
  views: ReplayView[];
  currentIndex: number;
  onSelect: (index: number) => void;
  /** Toàn bộ lượt xem của ca, kể cả lượt đang bị bộ lọc ẩn. */
  allViews?: ReplayView[];
  shortViewCount?: number;
  filtered?: boolean;
  minDwellMs?: number;
}) {
  const groups = groupByLesson(views);
  const occurrences = repeatOccurrences(allViews);
  const total = allViews.length;
  const countLabel = filtered
    ? `${views.length}/${total} lượt xem`
    : `${total} lượt xem trong ca`;
  const shortLabel = filtered
    ? `đã ẩn ${shortViewCount} lượt ngắn`
    : `${shortViewCount} lượt ngắn`;

  return (
    <div className="flex h-full min-h-0 flex-col rounded-[18px] border border-[#eeeee9] bg-white shadow-xs">
      <div className="border-b border-[#eeeee9] px-4 py-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-black/35">
          Dòng thời gian
        </p>
        <p className="mt-1 text-xs text-black/45">
          {countLabel}
          {shortLabel && (
            <>
              {" · "}
              <span className="text-[#8a6420]">{shortLabel}</span>
            </>
          )}
        </p>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {groups.map((group, groupIndex) => (
          <div
            key={`${group.lessonId}-${groupIndex}`}
            className="mb-3"
          >
            <p className="truncate px-2 py-1 text-[11px] font-semibold text-black/45">
              {group.title}
            </p>
            <div className="space-y-1">
              {group.items.map(({ view, index }) => {
                const active = index === currentIndex;
                const occurrence = occurrences.get(view.contentViewId) ?? 1;
                return (
                  <button
                    key={`${view.contentViewId}-${index}`}
                    type="button"
                    onClick={() => onSelect(index)}
                    aria-current={active ? "true" : undefined}
                    className={cn(
                      "flex w-full items-start gap-2 rounded-xl px-2.5 py-2 text-left transition-colors",
                      active
                        ? "bg-[#e8f1e6] text-[#2f4a2d]"
                        : "text-black/65 hover:bg-[#f7f8f4]",
                    )}
                  >
                    <Icon
                      name={
                        view.surface === "quiz"
                          ? "ri-list-check-3"
                          : "ri-slideshow-3-line"
                      }
                      className="mt-0.5 size-4 shrink-0"
                    />
                    <span className="min-w-0 flex-1">
                      <span className="flex min-w-0 items-center gap-1">
                        <span className="block truncate text-xs font-medium">
                          {view.slideTitle ||
                            (view.surface === "quiz" ? "Bài tập" : "Slide")}
                        </span>
                        {occurrence > 1 && (
                          <span className="shrink-0 rounded-full bg-[#f2f4ee] px-1.5 py-0.5 text-[9px] font-semibold text-black/45">
                            Lần {occurrence}
                          </span>
                        )}
                      </span>
                      <span className="mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-1 text-[10px] text-black/40">
                        <span>
                          {view.pageNumber ? `Trang ${view.pageNumber}` : "UI"}
                        </span>
                        <span>·</span>
                        <span>{formatDuration(viewDwellMs(view))}</span>
                        {!view.counted && (
                          <TimelineBadge tone="warning">
                            Ngắn &lt;{formatDwellThreshold(minDwellMs)}
                          </TimelineBadge>
                        )}
                        {view.sampleCount === 0 && (
                          <TimelineBadge tone="muted">Không có mẫu</TimelineBadge>
                        )}
                        {view.layouts.length === 0 && (
                          <TimelineBadge tone="danger">Thiếu layout</TimelineBadge>
                        )}
                        {view.analysisStatus !== "ready" &&
                          view.sampleCount > 0 && (
                            <span className="text-[#a26a2b]">chưa phân tích</span>
                          )}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
