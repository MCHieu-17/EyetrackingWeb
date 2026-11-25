"use client";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Switch } from "@/components/ui/switch";
import { formatDuration } from "./replay-geometry";
import type { PlaybackSpeed } from "./use-replay-player";

export function ReplayControls({
  playing,
  timeMs,
  duration,
  speed,
  speeds,
  autoAdvance,
  viewIndex,
  viewCount,
  onTogglePlay,
  onSeek,
  onSpeed,
  onAutoAdvance,
  onPreviousView,
  onNextView,
}: {
  playing: boolean;
  timeMs: number;
  duration: number;
  speed: PlaybackSpeed;
  speeds: readonly PlaybackSpeed[];
  autoAdvance: boolean;
  viewIndex: number;
  viewCount: number;
  onTogglePlay: () => void;
  onSeek: (ms: number) => void;
  onSpeed: (speed: PlaybackSpeed) => void;
  onAutoAdvance: (value: boolean) => void;
  onPreviousView: () => void;
  onNextView: () => void;
}) {
  return (
    <div className="space-y-3 rounded-[18px] border border-border bg-card p-3 shadow-xs">
      <div className="flex items-center gap-3">
        <Button
          type="button"
          size="icon"
          className="size-10 rounded-full bg-primary text-primary-foreground hover:bg-primary-hover"
          onClick={onTogglePlay}
          disabled={duration <= 0}
          aria-label={playing ? "Tạm dừng" : "Phát"}
        >
          <Icon name={playing ? "ri-pause-line" : "ri-play-line"} className="size-4" />
        </Button>
        <Button
          type="button"
          variant="outline"
          size="icon-sm"
          className="rounded-full border-border bg-card"
          onClick={onPreviousView}
          disabled={viewIndex <= 0}
          aria-label="View trước"
        >
          <Icon name="ri-arrow-left-s-line" className="size-4" />
        </Button>
        <Button
          type="button"
          variant="outline"
          size="icon-sm"
          className="rounded-full border-border bg-card"
          onClick={onNextView}
          disabled={viewIndex >= viewCount - 1}
          aria-label="View kế tiếp"
        >
          <Icon name="ri-arrow-right-s-line" className="size-4" />
        </Button>
        <span className="ml-1 shrink-0 text-xs tabular-nums text-muted-foreground">
          {formatDuration(timeMs)} / {formatDuration(duration)}
        </span>
        <input
          type="range"
          min={0}
          max={Math.max(1, duration)}
          step={100}
          value={Math.min(duration, timeMs)}
          onChange={(event) => onSeek(Number(event.target.value))}
          className="min-w-0 flex-1 accent-[var(--primary)]"
          aria-label="Tua thời gian trong lượt xem"
        />
        <label className="flex shrink-0 items-center gap-1.5 text-xs text-muted-foreground">
          <span className="sr-only">Tốc độ phát</span>
          <select
            value={speed}
            onChange={(event) => onSpeed(Number(event.target.value) as PlaybackSpeed)}
            className="h-8 rounded-full border border-border bg-muted/40 px-2 text-xs font-semibold text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
            aria-label="Tốc độ phát"
          >
            {speeds.map((value) => (
              <option key={value} value={value}>
                {value}x
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
        <label className="flex items-center gap-2">
          <Switch
            checked={autoAdvance}
            onCheckedChange={onAutoAdvance}
            ariaLabel="Tự chuyển sang lượt xem kế tiếp"
          />
          Tự chuyển view
        </label>
        <span>
          View {viewCount === 0 ? 0 : viewIndex + 1}/{viewCount}
        </span>
        <span className="ml-auto hidden sm:inline">
          Phím tắt: Space phát/tạm dừng · ←/→ tua 1 giây
        </span>
      </div>
    </div>
  );
}
