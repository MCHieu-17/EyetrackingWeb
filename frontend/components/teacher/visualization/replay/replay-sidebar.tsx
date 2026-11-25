"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/utils";
import type {
  ReplayAoiStat,
  ReplaySample,
  ReplayView,
} from "@/lib/types/visualization";
import {
  formatDuration,
  isNoLabel,
  labelDomain,
  NO_LABEL_SLIDE,
  NO_LABEL_UI,
} from "./replay-geometry";

function labelTone(label: string): string {
  if (label === NO_LABEL_SLIDE || label === NO_LABEL_UI) {
    return "border-destructive/20 bg-destructive/10 text-destructive";
  }
  return labelDomain(label) === "slide"
    ? "border-success/25 bg-accent text-success"
    : "border-warning/25 bg-warning/10 text-warning";
}

function statsForView(view: ReplayView): ReplayAoiStat[] {
  const byLabel = new Map(view.aoiStats.map((item) => [item.label, item]));
  for (const aoi of view.slideAois) {
    if (!aoi.analysisLabel || aoi.isContainer) continue;
    if (!byLabel.has(aoi.analysisLabel)) {
      byLabel.set(aoi.analysisLabel, {
        label: aoi.analysisLabel,
        name: aoi.name,
        domain: "slide",
        durationMs: 0,
        sampleCount: 0,
      });
    }
  }
  return [...byLabel.values()].sort(
    (a, b) => b.durationMs - a.durationMs || a.label.localeCompare(b.label),
  );
}

export function ReplaySidebar({
  courseId,
  view,
  currentSample,
  pinnedLabel,
  onPin,
  onSeekLabel,
  onRebuild,
  rebuilding,
}: {
  courseId: string;
  view: ReplayView;
  currentSample: ReplaySample | null;
  pinnedLabel: string | null;
  onPin: (label: string | null) => void;
  onSeekLabel: (label: string) => void;
  onRebuild: () => void;
  rebuilding: boolean;
}) {
  const activeLabel = pinnedLabel ?? currentSample?.aoiLabel ?? null;
  const stats = statsForView(view);
  const label = currentSample?.aoiLabel ?? null;
  const aoiHref =
    view.slideId
      ? `/teacher/courses/${courseId}?tab=aoi&lesson=${view.lessonId}&slide=${view.slideId}`
      : `/teacher/courses/${courseId}?tab=aoi&lesson=${view.lessonId}`;

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 overflow-y-auto">
      <div className="rounded-[18px] border border-border bg-card p-4 shadow-xs">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
              Mẫu hiện tại
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {currentSample
                ? formatDuration(currentSample.offsetMs)
                : "Chưa có mẫu"}
            </p>
          </div>
          {currentSample && (
            <Badge
              variant={currentSample.status === "ok" ? "success" : "warning"}
              className="shrink-0"
            >
              {currentSample.status === "ok"
                ? "Hợp lệ"
                : currentSample.status === "no_face"
                  ? "Mất dấu"
                  : currentSample.status === "offscreen"
                    ? "Ngoài màn hình"
                    : "Lỗi"}
            </Badge>
          )}
        </div>

        <div className="mt-3">
          {label ? (
            <span
              className={cn(
                "inline-flex max-w-full items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold",
                labelTone(label),
              )}
            >
              <span className="truncate">{label}</span>
            </span>
          ) : (
            <span className="text-xs text-muted-foreground">Chưa có nhãn AOI</span>
          )}
        </div>

        {isNoLabel(label) && (
          <div className="mt-3 rounded-[14px] border border-destructive/20 bg-destructive/10 p-3 text-xs leading-5 text-destructive">
            <p className="font-semibold">Điểm nhìn chưa thuộc vùng nào</p>
            <p className="mt-1 text-destructive/75">
              {label === NO_LABEL_SLIDE
                ? "Điểm nằm trong slide nhưng ngoài mọi AOI leaf. Hãy kiểm tra lại vùng đã vẽ."
                : "Điểm nằm ngoài slide và ngoài mọi AOI giao diện."}
            </p>
            <Button
              asChild
              size="xs"
              variant="outline"
              className="mt-2 rounded-full border-destructive/20 bg-card"
            >
              <Link href={aoiHref}>
                <Icon name="ri-edit-line" className="size-3.5" />
                Mở vùng phân tích
              </Link>
            </Button>
          </div>
        )}

        {currentSample && (
          <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-[11px]">
            <div>
              <dt className="text-muted-foreground">Toạ độ viewport</dt>
              <dd className="mt-0.5 tabular-nums text-muted-foreground">
                {currentSample.viewportX?.toFixed(3) ?? "—"},{" "}
                {currentSample.viewportY?.toFixed(3) ?? "—"}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Trong slide</dt>
              <dd className="mt-0.5 tabular-nums text-muted-foreground">
                {currentSample.slideX?.toFixed(3) ?? "—"},{" "}
                {currentSample.slideY?.toFixed(3) ?? "—"}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Layout</dt>
              <dd className="mt-0.5 truncate text-muted-foreground">
                {currentSample.layoutId ? currentSample.layoutId.slice(0, 8) : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Trạng thái phân tích</dt>
              <dd className="mt-0.5 text-muted-foreground">
                {view.analysisStatus === "ready" ? "Đã phân tích" : "Chưa xong"}
              </dd>
            </div>
          </dl>
        )}
      </div>

      <div className="rounded-[18px] border border-border bg-card p-3 shadow-xs">
        <div className="flex items-center justify-between gap-2 px-1">
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            Thống kê AOI
          </p>
          {pinnedLabel && (
            <button
              type="button"
              onClick={() => onPin(null)}
              className="text-[11px] font-medium text-muted-foreground hover:text-foreground"
            >
              Bỏ ghim
            </button>
          )}
        </div>
        <div className="mt-2 space-y-1">
          {stats.length === 0 ? (
            <p className="px-1 py-4 text-center text-xs text-muted-foreground">
              Chưa có thống kê cho lượt xem này.
            </p>
          ) : (
            stats.map((item) => {
              const active = item.label === activeLabel;
              return (
                <div
                  key={item.label}
                  className={cn(
                    "flex items-center gap-2 rounded-xl px-2 py-1.5 transition-colors",
                    active ? "bg-accent" : "hover:bg-muted/60",
                  )}
                >
                  <span
                    className={cn(
                      "size-2 shrink-0 rounded-full",
                      item.domain === "slide" ? "bg-primary" : "bg-warning",
                      isNoLabel(item.label) && "bg-[var(--chart-8)]",
                    )}
                  />
                  <button
                    type="button"
                    onClick={() => {
                      onPin(item.label);
                      onSeekLabel(item.label);
                    }}
                    className="min-w-0 flex-1 truncate text-left text-xs text-muted-foreground hover:text-foreground"
                    title={`${item.name} · ${item.label}`}
                  >
                    {item.name}
                  </button>
                  <span className="shrink-0 text-[10px] tabular-nums text-muted-foreground">
                    {formatDuration(item.durationMs)}
                  </span>
                  <span className="w-8 shrink-0 text-right text-[10px] tabular-nums text-muted-foreground">
                    {item.sampleCount}
                  </span>
                </div>
              );
            })
          )}
        </div>
      </div>

      {view.layouts.length === 0 && (
        <div className="rounded-[18px] border border-destructive/20 bg-destructive/10 p-4 text-xs text-destructive">
          <p className="font-semibold">Thiếu layout gốc</p>
          <p className="mt-1 leading-5">
            Lượt xem này không có `view_layout` nên không thể kiểm tra vị trí
            slide/vùng UI. Dữ liệu gaze thô vẫn còn.
          </p>
        </div>
      )}

      {view.analysisStatus !== "ready" && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="w-full rounded-full border-border bg-card"
          onClick={onRebuild}
          disabled={rebuilding}
        >
          <Icon name="ri-refresh-line" className="size-4" />
          {rebuilding ? "Đang gửi…" : "Phân tích lại bài này"}
        </Button>
      )}
    </div>
  );
}
