"use client";

import * as React from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { formatDuration, type QueryHistoryItem } from "@/lib/admin-db";
import { formatDateTimeVN } from "@/lib/utils";

interface QueryHistoryProps {
  items: QueryHistoryItem[];
  onSelect: (item: QueryHistoryItem) => void;
  onClear: () => void;
}

export function QueryHistory({ items, onSelect, onClear }: QueryHistoryProps) {
  const [confirmOpen, setConfirmOpen] = React.useState(false);

  if (items.length === 0) {
    return (
      <EmptyState
        icon="ri-history-line"
        title="Chưa có lịch sử"
        description="Các truy vấn bạn chạy sẽ xuất hiện ở đây."
        className="border-0 shadow-none"
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          {items.length} truy vấn gần nhất
        </p>
        <Button
          variant="ghost"
          size="xs"
          onClick={() => setConfirmOpen(true)}
        >
          <Icon name="ri-delete-bin-line" />
          Xóa lịch sử
        </Button>
      </div>

      <div className="space-y-2">
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onSelect(item)}
            className="w-full rounded-xl border border-[#eeeee9] bg-white p-3 text-left transition-colors hover:bg-muted/40"
          >
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={item.ok ? "success" : "destructive"}>
                {item.ok ? "Thành công" : "Lỗi"}
              </Badge>
              <span className="text-[11px] text-muted-foreground">
                {formatDateTimeVN(item.ranAt)}
              </span>
              <span className="ml-auto text-[11px] text-muted-foreground">
                {formatDuration(item.durationMs)} · {item.rowCount} dòng
              </span>
            </div>
            <pre className="mt-2 line-clamp-2 whitespace-pre-wrap break-words font-mono text-[11px] text-foreground">
              {item.sql}
            </pre>
            {item.error && (
              <p className="mt-1 line-clamp-1 text-[11px] text-destructive">
                {item.error}
              </p>
            )}
          </button>
        ))}
      </div>

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Xóa lịch sử truy vấn?"
        description="Toàn bộ lịch sử lưu trên trình duyệt sẽ bị xóa."
        confirmLabel="Xóa"
        destructive
        onConfirm={() => {
          onClear();
          setConfirmOpen(false);
        }}
      />
    </div>
  );
}
