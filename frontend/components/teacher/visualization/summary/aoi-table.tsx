"use client";

import { Badge } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icon";
import type { AoiSummaryAoi } from "@/lib/types/visualization";
import { formatDuration } from "../replay/replay-geometry";

export function AoiTable({ rows }: { rows: AoiSummaryAoi[] }) {
  if (rows.length === 0) {
    return (
      <p className="px-4 py-10 text-center text-sm text-muted-foreground">
        Chưa có dữ liệu AOI.
      </p>
    );
  }

  return (
    <div className="max-h-[420px] overflow-auto rounded-[16px] border border-border">
      <table className="w-full min-w-[680px] border-collapse text-left text-xs">
        <thead className="sticky top-0 z-10 bg-muted/40 text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
          <tr>
            <th className="px-3 py-2 font-semibold">Vùng</th>
            <th className="px-3 py-2 font-semibold">Nhóm</th>
            <th className="px-3 py-2 text-right font-semibold">Thời lượng</th>
            <th className="px-3 py-2 text-right font-semibold">Tỷ lệ</th>
            <th className="px-3 py-2 text-right font-semibold">Mẫu</th>
            <th className="px-3 py-2 text-right font-semibold">Học viên</th>
            <th className="px-3 py-2 text-right font-semibold">Slide</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((row) => (
            <tr key={row.label} className="hover:bg-muted/60">
              <td className="max-w-[280px] px-3 py-2">
                <p className="truncate font-medium text-muted-foreground" title={row.label}>
                  {row.name}
                </p>
                <p className="truncate text-[10px] text-muted-foreground" title={row.label}>
                  {row.label}
                </p>
              </td>
              <td className="px-3 py-2">
                <span className="inline-flex items-center gap-1.5 text-muted-foreground">
                  <span
                    className={`size-2 rounded-full ${
                      row.isUnlabeled
                        ? "bg-[var(--chart-8)]"
                        : row.domain === "slide"
                          ? "bg-primary"
                          : "bg-warning"
                    }`}
                  />
                  {row.isUnlabeled
                    ? "Chưa đánh dấu"
                    : row.domain === "slide"
                      ? "Slide"
                      : "Giao diện"}
                </span>
              </td>
              <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums text-muted-foreground">
                {formatDuration(row.durationMs)}
              </td>
              <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums text-muted-foreground">
                {(row.share * 100).toFixed(1)}%
              </td>
              <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">
                {row.sampleCount}
              </td>
              <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">
                {row.studentCount}
              </td>
              <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">
                <span className="inline-flex items-center gap-1">
                  {row.slideCount}
                  {row.mixedSlides && (
                    <span title="Nhãn xuất hiện trên nhiều slide">
                      <Icon
                        name="ri-error-warning-line"
                        className="size-3.5 text-warning"
                      />
                    </span>
                  )}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex items-center justify-between border-t border-border px-3 py-2 text-[10px] text-muted-foreground">
        <span>{rows.length} nhãn</span>
        <Badge variant="secondary" className="font-normal">
          Đơn vị: thời lượng ghi nhận hợp lệ
        </Badge>
      </div>
    </div>
  );
}
