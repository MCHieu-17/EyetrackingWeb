"use client";

import { Icon } from "@/components/ui/icon";
import type { AoiSummaryAoi } from "@/lib/types/visualization";
import { formatDuration } from "../replay/replay-geometry";
import { aoiColor, percent, topAois } from "./summary-helpers";

export function AoiBarChart({
  aois,
  totalMs,
}: {
  aois: AoiSummaryAoi[];
  totalMs: number;
}) {
  const rows = topAois(aois, 12);
  if (rows.length === 0 || totalMs <= 0) {
    return (
      <p className="px-4 py-10 text-center text-sm text-muted-foreground">
        Chưa có thời lượng AOI để hiển thị.
      </p>
    );
  }

  return (
    <div className="space-y-2.5">
      {rows.map((aoi) => {
        const width = percent(aoi.durationMs, totalMs);
        return (
          <div key={aoi.label} className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-1">
            <div className="flex min-w-0 items-center gap-1.5">
              <span
                className="size-2 shrink-0 rounded-full"
                style={{ backgroundColor: aoiColor(aoi) }}
              />
              <span className="truncate text-xs font-medium text-muted-foreground">
                {aoi.name}
              </span>
              {aoi.mixedSlides && (
                <Icon
                  name="ri-error-warning-line"
                  className="size-3.5 shrink-0 text-warning"
                />
              )}
              {aoi.isUnlabeled && (
                <span className="shrink-0 rounded-full bg-destructive/10 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-destructive">
                  no label
                </span>
              )}
            </div>
            <span className="text-right text-[11px] tabular-nums text-muted-foreground">
              {formatDuration(aoi.durationMs)} · {Math.round(aoi.share * 100)}%
            </span>
            <div className="col-span-2 h-2 overflow-hidden rounded-full bg-chart-track">
              <div
                className="h-full rounded-full transition-[width]"
                style={{
                  width: `${width}%`,
                  backgroundColor: aoiColor(aoi),
                  minWidth: width > 0 ? 2 : 0,
                }}
              />
            </div>
          </div>
        );
      })}
      <div className="flex items-center justify-between border-t border-border pt-2 text-[11px] text-muted-foreground">
        <span>{aois.length} nhãn AOI</span>
        <span>Tổng {formatDuration(totalMs)}</span>
      </div>
    </div>
  );
}
