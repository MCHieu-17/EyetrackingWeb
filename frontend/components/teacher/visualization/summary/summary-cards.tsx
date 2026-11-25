"use client";

import { Icon } from "@/components/ui/icon";
import type { AoiSummaryTotals } from "@/lib/types/visualization";
import { formatDuration } from "../replay/replay-geometry";
import { percent } from "./summary-helpers";

export function SummaryCards({ totals }: { totals: AoiSummaryTotals }) {
  const total = totals.trackedDurationMs;
  const cards = [
    {
      label: "Tổng thời gian ghi nhận",
      value: formatDuration(total),
      hint: `${totals.gazeSampleCount} mẫu gaze`,
      icon: "ri-history-line",
      tone: "bg-accent text-primary",
    },
    {
      label: "Trong slide",
      value: `${percent(totals.slideDurationMs, total).toFixed(0)}%`,
      hint: formatDuration(totals.slideDurationMs),
      icon: "ri-slideshow-3-line",
      tone: "bg-accent text-primary",
    },
    {
      label: "Vùng giao diện",
      value: `${percent(totals.uiDurationMs, total).toFixed(0)}%`,
      hint: formatDuration(totals.uiDurationMs),
      icon: "ri-layout-left-line",
      tone: "bg-warning/10 text-warning",
    },
    {
      label: "Chưa đánh dấu",
      value: `${percent(totals.unlabeledDurationMs, total).toFixed(0)}%`,
      hint: formatDuration(totals.unlabeledDurationMs),
      icon: "ri-error-warning-line",
      tone: "bg-destructive/10 text-destructive",
    },
    {
      label: "Phạm vi dữ liệu",
      value: `${totals.visitCount} ca`,
      hint: `${totals.studentCount} học viên · ${totals.contentViewCount} lượt xem`,
      icon: "ri-group-line",
      tone: "bg-muted text-foreground/75",
    },
  ];

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      {cards.map((card) => (
        <div
          key={card.label}
          className="rounded-2xl border border-border bg-card p-4 shadow-sm"
        >
          <div className="flex items-start justify-between gap-2">
            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
              {card.label}
            </p>
            <span
              className={`flex size-8 shrink-0 items-center justify-center rounded-full ${card.tone}`}
            >
              <Icon name={card.icon} className="size-4" />
            </span>
          </div>
          <p className="mt-3 font-display text-2xl font-semibold tracking-[-0.03em] text-foreground">
            {card.value}
          </p>
          <p className="mt-1 text-[11px] text-muted-foreground">{card.hint}</p>
        </div>
      ))}
    </div>
  );
}
