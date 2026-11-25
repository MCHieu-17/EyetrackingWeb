"use client";

import type { AoiSummaryVisit } from "@/lib/types/visualization";
import { formatDuration } from "../replay/replay-geometry";
import { maxOf, visitTrend } from "./summary-helpers";

export function VisitTrendChart({ visits }: { visits: AoiSummaryVisit[] }) {
  const points = visitTrend(visits);
  if (points.length === 0) {
    return (
      <p className="px-4 py-10 text-center text-sm text-muted-foreground">
        Chưa có ca học để vẽ xu hướng.
      </p>
    );
  }

  const width = 640;
  const height = 180;
  const pad = 22;
  const max = maxOf(points);
  const x = (index: number) =>
    pad + (points.length === 1 ? (width - pad * 2) / 2 : (index / (points.length - 1)) * (width - pad * 2));
  const y = (value: number) =>
    height - pad - (value / max) * (height - pad * 2);
  const trackedLine = points.map((point, index) => `${x(index)},${y(point.tracked)}`).join(" ");
  const slideLine = points.map((point, index) => `${x(index)},${y(point.slide)}`).join(" ");

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-4 text-[11px] text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <span className="size-2 rounded-full bg-[var(--chart-1)]" /> Tổng ghi nhận
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="size-2 rounded-full bg-[var(--chart-2)]" /> Trong slide
        </span>
        <span className="ml-auto">{points.length} ca</span>
      </div>
      <div className="overflow-x-auto">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="h-48 w-full min-w-[520px]"
          role="img"
          aria-label="Xu hướng thời lượng nhìn theo ca học"
        >
          <line
            x1={pad}
            y1={height - pad}
            x2={width - pad}
            y2={height - pad}
            stroke="var(--chart-grid)"
            strokeWidth="1"
          />
          <line
            x1={pad}
            y1={pad}
            x2={pad}
            y2={height - pad}
            stroke="var(--chart-grid)"
            strokeWidth="1"
          />
          <polyline
            points={slideLine}
            fill="none"
            stroke="var(--chart-2)"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <polyline
            points={trackedLine}
            fill="none"
            stroke="var(--chart-1)"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          {points.map((point, index) => (
            <g key={point.visit.visitId}>
              <circle
                cx={x(index)}
                cy={y(point.tracked)}
                r="3.5"
                fill="var(--chart-1)"
                stroke="var(--card)"
                strokeWidth="2"
              >
                <title>
                  {point.visit.studentName} ·{" "}
                  {new Date(point.visit.startedAt).toLocaleString("vi-VN")} ·{" "}
                  {formatDuration(point.tracked)}
                </title>
              </circle>
            </g>
          ))}
        </svg>
      </div>
      <div className="flex justify-between text-[10px] text-muted-foreground">
        <span>{new Date(points[0].visit.startedAt).toLocaleDateString("vi-VN")}</span>
        <span>
          {new Date(points.at(-1)!.visit.startedAt).toLocaleDateString("vi-VN")}
        </span>
      </div>
      <p className="text-[10px] text-muted-foreground">
        Đỉnh cao nhất: {formatDuration(max)} · Đường đậm là tổng thời gian ghi
        nhận, đường nhạt là thời gian trong slide.
      </p>
    </div>
  );
}
