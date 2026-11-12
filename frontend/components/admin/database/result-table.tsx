"use client";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import type { AdminDbQueryResult } from "@/lib/api/admin-db";
import { ApiError } from "@/lib/api/client";
import { formatDuration } from "@/lib/admin-db";
import { DataTable } from "./data-table";
import { QueryErrorPanel } from "./query-error-panel";

interface ResultTableProps {
  result: AdminDbQueryResult | null;
  error: ApiError | null;
  isRunning: boolean;
  onExportCsv: () => void;
  onExportJson: () => void;
  onCopy: () => void;
}

export function ResultTable({
  result,
  error,
  isRunning,
  onExportCsv,
  onExportJson,
  onCopy,
}: ResultTableProps) {
  if (isRunning) {
    return (
      <div className="flex min-h-[220px] flex-col items-center justify-center gap-3 text-muted-foreground">
        <Spinner className="size-6" />
        <p className="text-sm">Đang chạy truy vấn...</p>
      </div>
    );
  }

  if (error) {
    return <QueryErrorPanel error={error} />;
  }

  if (!result) {
    return (
      <EmptyState
        icon="ri-play-circle-line"
        title="Chưa có kết quả"
        description="Chạy một truy vấn để xem dữ liệu."
        className="border-0 shadow-none"
      />
    );
  }

  if (result.rows.length === 0) {
    return (
      <EmptyState
        icon="ri-inbox-line"
        title="Không có dòng nào"
        description="Câu lệnh chạy thành công nhưng không trả về dữ liệu."
        className="border-0 shadow-none"
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <Badge variant="success">{result.rowCount} dòng</Badge>
        <span>{formatDuration(result.durationMs)}</span>
        <span>· Giới hạn {result.limit}</span>
        {result.truncated && <Badge variant="warning">Đã cắt bớt</Badge>}
        <div className="ml-auto flex items-center gap-2">
          <Button variant="outline" size="xs" onClick={onExportCsv}>
            <Icon name="ri-download-line" />
            CSV
          </Button>
          <Button variant="outline" size="xs" onClick={onExportJson}>
            <Icon name="ri-download-line" />
            JSON
          </Button>
          <Button variant="ghost" size="xs" onClick={onCopy}>
            <Icon name="ri-file-copy-line" />
            Copy
          </Button>
        </div>
      </div>

      {result.truncated && (
        <Alert variant="warning" title="Kết quả đã đạt giới hạn">
          {result.limit} dòng đầu tiên được hiển thị. Thêm WHERE hoặc LIMIT để
          thu hẹp kết quả.
        </Alert>
      )}

      <DataTable columns={result.columns} rows={result.rows} />
    </div>
  );
}
