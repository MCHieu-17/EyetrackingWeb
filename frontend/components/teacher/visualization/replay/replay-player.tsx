"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Switch } from "@/components/ui/switch";
import { useReplaySamples } from "@/hooks/use-visualization";
import { rebuildAoiHits } from "@/lib/api/aoi";
import { queryKeys } from "@/lib/query-keys";
import type { VisitReplay } from "@/lib/types/visualization";
import { ReplayControls } from "./replay-controls";
import { ReplaySidebar } from "./replay-sidebar";
import { ReplayStage } from "./replay-stage";
import { ReplayTimeline } from "./replay-timeline";
import {
  findSampleAt,
  firstSampleForLabel,
  formatDateTime,
  formatDwellThreshold,
  formatDuration,
  viewDwellMs,
} from "./replay-geometry";
import { useReplayPlayer } from "./use-replay-player";

export function ReplayPlayer({
  courseId,
  replay,
}: {
  courseId: string;
  replay: VisitReplay;
}) {
  const allViews = replay.views;
  const minDwellMs = replay.visit.minDwellMs ?? 1000;
  const [onlyCounted, setOnlyCounted] = useState(false);
  const views = useMemo(
    () => (onlyCounted ? allViews.filter((view) => view.counted) : allViews),
    [allViews, onlyCounted],
  );
  // Tính trực tiếp từ views để header, timeline và badge luôn khớp nhau.
  const shortViewCount = useMemo(
    () => allViews.filter((view) => !view.counted).length,
    [allViews],
  );
  const queryClient = useQueryClient();
  const player = useReplayPlayer(views);
  const [rebuilding, setRebuilding] = useState(false);
  const [showAllAois, setShowAllAois] = useState(true);
  const [showLabels, setShowLabels] = useState(true);
  const [showTrail, setShowTrail] = useState(false);
  const [pinned, setPinned] = useState<{
    viewId: string;
    label: string;
  } | null>(null);

  const currentView = player.currentView;
  const pinnedLabel =
    pinned && pinned.viewId === currentView?.contentViewId ? pinned.label : null;
  const setPinnedLabel = (label: string | null) => {
    setPinned(
      label && currentView
        ? { viewId: currentView.contentViewId, label }
        : null,
    );
  };
  const samplesQuery = useReplaySamples(
    replay.visit.visitId,
    currentView?.contentViewId ?? null,
  );

  const { hasNextPage, isFetchingNextPage, fetchNextPage } = samplesQuery;
  useEffect(() => {
    if (hasNextPage && !isFetchingNextPage) {
      void fetchNextPage();
    }
  }, [fetchNextPage, hasNextPage, isFetchingNextPage]);

  const samples = useMemo(
    () => samplesQuery.data?.pages.flatMap((page) => page.samples) ?? [],
    [samplesQuery.data],
  );
  const currentSample = findSampleAt(samples, player.timeMs);

  const playerRef = useRef(player);
  useEffect(() => {
    playerRef.current = player;
  });
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (
        target &&
        ["INPUT", "SELECT", "TEXTAREA", "BUTTON"].includes(target.tagName)
      ) {
        return;
      }
      const latest = playerRef.current;
      if (event.code === "Space") {
        event.preventDefault();
        latest.togglePlay();
      } else if (event.code === "ArrowLeft") {
        event.preventDefault();
        latest.seek(latest.timeMs - (event.shiftKey ? 5000 : 1000));
      } else if (event.code === "ArrowRight") {
        event.preventDefault();
        latest.seek(latest.timeMs + (event.shiftKey ? 5000 : 1000));
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  if (allViews.length === 0) {
    return (
      <EmptyState
        icon="ri-focus-2-line"
        title="Ca học chưa có lượt xem"
        description="Học viên có thể chưa mở slide nào trong ca này. Dữ liệu sẽ xuất hiện sau khi phiên học được ghi nhận."
      />
    );
  }

  const seekToLabel = (label: string) => {
    const sample = firstSampleForLabel(samples, label);
    if (sample) player.seek(sample.offsetMs);
  };

  const rebuild = async () => {
    if (!currentView) return;
    setRebuilding(true);
    try {
      await rebuildAoiHits({ courseId, lessonId: currentView.lessonId });
      window.setTimeout(() => {
        void queryClient.invalidateQueries({
          queryKey: queryKeys.visualization.visitReplay(replay.visit.visitId),
        });
        // Sample chứa aoiLabel/slideX/Y đã được worker tính lại; không xóa
        // cache này thì chấm gaze vẫn mang nhãn AOI cũ.
        void queryClient.invalidateQueries({
          queryKey: queryKeys.visualization.replaySamplesRoot(
            replay.visit.visitId,
          ),
        });
      }, 4000);
    } catch {
      // Lỗi mạng được phản ánh khi người dùng làm mới ca học.
    } finally {
      setRebuilding(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-border pb-5">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            Xem lại ca học
          </p>
          <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-foreground sm:text-3xl">
            {replay.student.name}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {replay.student.code || replay.student.email || "—"} ·{" "}
            {formatDateTime(replay.visit.startedAt)}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <Badge variant={replay.visit.status === "ended" ? "secondary" : "success"}>
            {replay.visit.status === "ended"
              ? "Đã kết thúc"
              : replay.visit.status === "active"
                ? "Đang diễn ra"
                : "Hết hạn"}
          </Badge>
          <span>{replay.visit.lessonSessionCount} bài</span>
          <span>·</span>
          <span>{allViews.length} lượt xem</span>
          {onlyCounted && (
            <>
              <span>·</span>
              <span>{views.length} đang hiển thị</span>
            </>
          )}
          <span>·</span>
          <span className="text-warning">{shortViewCount} lượt ngắn</span>
          <span>·</span>
          <span>{formatDuration(replay.visit.trackedDurationMs)}</span>
          <span>·</span>
          <span>{replay.visit.gazeCount} gaze</span>
          <div className="flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5">
            <Switch
              checked={onlyCounted}
              onCheckedChange={setOnlyCounted}
              ariaLabel="Chỉ lượt >= ngưỡng"
            />
            <span className="text-[11px] font-semibold text-muted-foreground">
              {"Chỉ lượt >= ngưỡng"}
            </span>
          </div>
        </div>
      </div>

      {views.length === 0 || !currentView ? (
        <EmptyState
          icon="ri-filter-off-line"
          title="Không có lượt xem đạt ngưỡng"
          description="Tất cả lượt xem trong ca đều ngắn hơn ngưỡng thời lượng. Bỏ bộ lọc để xem toàn bộ ca học."
          action={
            <Button
              type="button"
              variant="outline"
              className="rounded-full border-border bg-card"
              onClick={() => setOnlyCounted(false)}
            >
              <Icon name="ri-filter-off-line" className="size-4" />
              Xem tất cả lượt
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[250px_minmax(0,1fr)_310px]">
          <div className="min-h-0 lg:h-[calc(100dvh-250px)]">
            <ReplayTimeline
              views={views}
              allViews={allViews}
              shortViewCount={shortViewCount}
              minDwellMs={minDwellMs}
              filtered={onlyCounted}
              currentIndex={player.index}
              onSelect={player.selectView}
            />
          </div>

          <div className="min-w-0 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex rounded-full border border-border bg-card p-1">
                <button
                  type="button"
                  onClick={() => setShowAllAois((value) => !value)}
                  className="rounded-full px-3 py-1.5 text-xs font-semibold text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  {showAllAois ? "Chỉ vùng đang nhìn" : "Hiện tất cả vùng"}
                </button>
                <button
                  type="button"
                  onClick={() => setShowLabels((value) => !value)}
                  className="rounded-full px-3 py-1.5 text-xs font-semibold text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  {showLabels ? "Ẩn nhãn" : "Hiện nhãn"}
                </button>
                <button
                  type="button"
                  onClick={() => setShowTrail((value) => !value)}
                  className="rounded-full px-3 py-1.5 text-xs font-semibold text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  {showTrail ? "Ẩn vệt nhìn" : "Vệt nhìn 2s"}
                </button>
              </div>
              {pinnedLabel && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-accent px-3 py-1.5 text-xs font-semibold text-success">
                  <Icon name="ri-focus-2-line" className="size-3.5" />
                  Đang ghim: {pinnedLabel}
                </span>
              )}
              <span className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
                {formatDuration(viewDwellMs(currentView))} ·{" "}
                {currentView.sampleCount} mẫu
                {!currentView.counted && (
                  <span className="rounded-full bg-warning/10 px-1.5 py-0.5 text-[9px] font-semibold text-warning">
                    Ngắn &lt;{formatDwellThreshold(minDwellMs)}
                  </span>
                )}
              </span>
            </div>

            <ReplayStage
              view={currentView}
              samples={samples}
              currentSample={currentSample}
              showAllAois={showAllAois}
              showLabels={showLabels}
              showTrail={showTrail}
              pinnedLabel={pinnedLabel}
            />

            <ReplayControls
              playing={player.playing}
              timeMs={player.timeMs}
              duration={player.duration}
              speed={player.speed}
              speeds={player.speeds}
              autoAdvance={player.autoAdvance}
              viewIndex={player.index}
              viewCount={views.length}
              onTogglePlay={player.togglePlay}
              onSeek={player.seek}
              onSpeed={player.setSpeed}
              onAutoAdvance={player.setAutoAdvance}
              onPreviousView={player.previousView}
              onNextView={player.nextView}
            />

            {samplesQuery.isLoading && (
              <p className="text-center text-xs text-muted-foreground">Đang tải mẫu gaze…</p>
            )}
            {samplesQuery.isError && (
              <p className="text-center text-xs text-destructive">
                Không tải được mẫu gaze của lượt xem này.
              </p>
            )}
          </div>

          <div className="min-h-0 lg:h-[calc(100dvh-250px)]">
            <ReplaySidebar
              courseId={courseId}
              view={currentView}
              currentSample={currentSample}
              pinnedLabel={pinnedLabel}
              onPin={setPinnedLabel}
              onSeekLabel={seekToLabel}
              onRebuild={() => void rebuild()}
              rebuilding={rebuilding}
            />
          </div>
        </div>
      )}
    </div>
  );
}
