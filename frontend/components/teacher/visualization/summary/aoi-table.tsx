"use client";

import { Badge } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icon";
import type { AoiSummaryAoi } from "@/lib/types/visualization";
import { formatDuration } from "../replay/replay-geometry";

export function AoiTable({ rows }: { rows: AoiSummaryAoi[] }) {
  if (rows.length === 0) {
    return (
      <p className="px-4 py-10 text-center text-sm text-black/40">
        Chưa có dữ liệu AOI.
      </p>
    );
  }

  return (
    <div className="max-h-[420px] overflow-auto rounded-[16px] border border-[#eeeee9]">
      <table className="w-full min-w-[680px] border-collapse text-left text-xs">
        <thead className="sticky top-0 z-10 bg-[#fdfdfa] text-[10px] uppercase tracking-[0.08em] text-black/40">
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
        <tbody className="divide-y divide-[#f0f1ec]">
          {rows.map((row) => (
            <tr key={row.label} className="hover:bg-[#fafbf8]">
              <td className="max-w-[280px] px-3 py-2">
                <p className="truncate font-medium text-black/70" title={row.label}>
                  {row.name}
                </p>
                <p className="truncate text-[10px] text-black/35" title={row.label}>
                  {row.label}
                </p>
              </td>
              <td className="px-3 py-2">
                <span className="inline-flex items-center gap-1.5 text-black/50">
                  <span
                    className={`size-2 rounded-full ${
                      row.isUnlabeled
                        ? "bg-[#a34a32]"
                        : row.domain === "slide"
                          ? "bg-[#36533a]"
                          : "bg-[#b45309]"
                    }`}
                  />
                  {row.isUnlabeled
                    ? "Chưa đánh dấu"
                    : row.domain === "slide"
                      ? "Slide"
                      : "Giao diện"}
                </span>
              </td>
              <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums text-black/60">
                {formatDuration(row.durationMs)}
              </td>
              <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums text-black/50">
                {(row.share * 100).toFixed(1)}%
              </td>
              <td className="px-3 py-2 text-right tabular-nums text-black/50">
                {row.sampleCount}
              </td>
              <td className="px-3 py-2 text-right tabular-nums text-black/50">
                {row.studentCount}
              </td>
              <td className="px-3 py-2 text-right tabular-nums text-black/50">
                <span className="inline-flex items-center gap-1">
                  {row.slideCount}
                  {row.mixedSlides && (
                    <span title="Nhãn xuất hiện trên nhiều slide">
                      <Icon
                        name="ri-error-warning-line"
                        className="size-3.5 text-[#a26a2b]"
                      />
                    </span>
                  )}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex items-center justify-between border-t border-[#eeeee9] px-3 py-2 text-[10px] text-black/35">
        <span>{rows.length} nhãn</span>
        <Badge variant="secondary" className="font-normal">
          Đơn vị: thời lượng ghi nhận hợp lệ
        </Badge>
      </div>
    </div>
  );
}
