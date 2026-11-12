"use client";

import * as React from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { useAdminDbTableRows } from "@/hooks/use-admin-db";
import type {
  AdminDbFilter,
  AdminDbFilterOperator,
  AdminDbTable,
  AdminDbTableRowsParams,
} from "@/lib/api/admin-db";
import { ApiError } from "@/lib/api/client";
import { formatDuration, shortTypeLabel } from "@/lib/admin-db";
import { DataTable } from "./data-table";
import { QueryErrorPanel } from "./query-error-panel";

interface TableBrowserProps {
  tables: AdminDbTable[];
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
  onRetry: () => void;
}

interface FilterRow {
  id: string;
  column: string;
  operator: AdminDbFilterOperator;
  value: string;
}

const FILTER_OPERATORS: { value: AdminDbFilterOperator; label: string }[] = [
  { value: "eq", label: "Bằng" },
  { value: "neq", label: "Khác" },
  { value: "gt", label: "Lớn hơn" },
  { value: "gte", label: "Lớn hơn hoặc bằng" },
  { value: "lt", label: "Nhỏ hơn" },
  { value: "lte", label: "Nhỏ hơn hoặc bằng" },
  { value: "contains", label: "Chứa" },
  { value: "starts_with", label: "Bắt đầu bằng" },
  { value: "ends_with", label: "Kết thúc bằng" },
  { value: "is_null", label: "Là NULL" },
  { value: "is_not_null", label: "Không phải NULL" },
];

const NULL_OPERATORS = new Set<AdminDbFilterOperator>([
  "is_null",
  "is_not_null",
]);

const PAGE_SIZES = [50, 100, 200];

function tableKey(table: AdminDbTable): string {
  return `${table.schema}.${table.name}`;
}

function newFilter(table: AdminDbTable): FilterRow {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    column: table.columns[0]?.name ?? "",
    operator: "eq",
    value: "",
  };
}

export function TableBrowser({
  tables,
  isLoading,
  isError,
  error,
  onRetry,
}: TableBrowserProps) {
  const [selectedKey, setSelectedKey] = React.useState("");
  const [selectedColumns, setSelectedColumns] = React.useState<string[]>([]);
  const [filters, setFilters] = React.useState<FilterRow[]>([]);
  const [debouncedFilters, setDebouncedFilters] = React.useState<FilterRow[]>(
    [],
  );
  const [orderBy, setOrderBy] = React.useState<string | null>(null);
  const [orderDir, setOrderDir] = React.useState<"asc" | "desc">("asc");
  const [limit, setLimit] = React.useState(50);
  const [offset, setOffset] = React.useState(0);
  const [columnsOpen, setColumnsOpen] = React.useState(false);

  const selectedTable = React.useMemo(
    () => tables.find((table) => tableKey(table) === selectedKey) ?? null,
    [tables, selectedKey],
  );

  React.useEffect(() => {
    const timeout = window.setTimeout(() => setDebouncedFilters(filters), 400);
    return () => window.clearTimeout(timeout);
  }, [filters]);

  const activeFilters = React.useMemo<AdminDbFilter[]>(
    () =>
      debouncedFilters
        .filter(
          (filter) =>
            NULL_OPERATORS.has(filter.operator) || filter.value !== "",
        )
        .map((filter) => ({
          column: filter.column,
          operator: filter.operator,
          value: NULL_OPERATORS.has(filter.operator) ? null : filter.value,
        })),
    [debouncedFilters],
  );

  const params = React.useMemo<AdminDbTableRowsParams | null>(() => {
    if (!selectedTable || selectedColumns.length === 0) return null;
    return {
      schema: selectedTable.schema,
      table: selectedTable.name,
      columns: selectedColumns,
      limit,
      offset,
      orderBy,
      orderDir,
      filters: activeFilters,
    };
  }, [
    selectedTable,
    selectedColumns,
    limit,
    offset,
    orderBy,
    orderDir,
    activeFilters,
  ]);

  const browseQuery = useAdminDbTableRows(params);
  const result = browseQuery.data;
  const browseError =
    browseQuery.error instanceof ApiError
      ? browseQuery.error
      : browseQuery.error instanceof Error
        ? new ApiError(0, browseQuery.error.message)
        : null;
  const page = Math.floor(offset / limit) + 1;

  const handleSelectTable = (key: string) => {
    setSelectedKey(key);
    const table = tables.find((item) => tableKey(item) === key) ?? null;
    setSelectedColumns(
      table ? table.columns.map((column) => column.name) : [],
    );
    setFilters([]);
    setDebouncedFilters([]);
    const primaryKey = table?.columns.find((column) => column.primaryKey);
    setOrderBy(primaryKey?.name ?? null);
    setOrderDir("asc");
    setOffset(0);
  };

  const handleToggleColumn = (name: string) => {
    setSelectedColumns((prev) =>
      prev.includes(name)
        ? prev.filter((item) => item !== name)
        : [...prev, name],
    );
    setOffset(0);
  };

  const handleSelectAllColumns = () => {
    if (!selectedTable) return;
    setSelectedColumns(selectedTable.columns.map((column) => column.name));
    setOffset(0);
  };

  const handleClearColumns = () => {
    setSelectedColumns([]);
    setOffset(0);
  };

  const handleAddFilter = () => {
    if (!selectedTable || filters.length >= 10) return;
    setFilters((prev) => [...prev, newFilter(selectedTable)]);
    setOffset(0);
  };

  const handleUpdateFilter = (id: string, patch: Partial<FilterRow>) => {
    setFilters((prev) =>
      prev.map((filter) =>
        filter.id === id ? { ...filter, ...patch } : filter,
      ),
    );
    setOffset(0);
  };

  const handleRemoveFilter = (id: string) => {
    setFilters((prev) => prev.filter((filter) => filter.id !== id));
    setOffset(0);
  };

  const handleOrderByChange = (value: string) => {
    setOrderBy(value || null);
    setOffset(0);
  };

  const handleOrderDirChange = (value: string) => {
    setOrderDir(value === "desc" ? "desc" : "asc");
    setOffset(0);
  };

  const handleLimitChange = (value: number) => {
    setLimit(value);
    setOffset(0);
  };

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-10 rounded-full" />
        <Skeleton className="h-24 rounded-[14px]" />
        <Skeleton className="h-64 rounded-[14px]" />
      </div>
    );
  }

  if (isError) {
    return (
      <ErrorState
        title="Không tải được schema"
        description={error instanceof Error ? error.message : "Vui lòng thử lại."}
        onRetry={onRetry}
        className="border-0 shadow-none"
      />
    );
  }

  if (tables.length === 0) {
    return (
      <EmptyState
        icon="ri-table-line"
        title="Không có bảng nào"
        description="Role truy vấn hiện tại không có quyền đọc bảng/view nào."
        className="border-0 shadow-none"
      />
    );
  }

  const tableItems = tables.filter(
    (table) => table.kind !== "view" && table.kind !== "materialized_view",
  );
  const viewItems = tables.filter(
    (table) => table.kind === "view" || table.kind === "materialized_view",
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-[220px] flex-1">
          <label
            htmlFor="admin-db-browse-table"
            className="mb-1 block text-xs font-medium text-muted-foreground"
          >
            Bảng / View
          </label>
          <select
            id="admin-db-browse-table"
            aria-label="Chọn bảng"
            value={selectedKey}
            onChange={(event) => handleSelectTable(event.target.value)}
            className="h-10 w-full rounded-full border border-border bg-surface px-3 text-sm text-foreground shadow-xs outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
          >
            <option value="">Chọn bảng...</option>
            {tableItems.length > 0 && (
              <optgroup label="Bảng">
                {tableItems.map((table) => (
                  <option key={tableKey(table)} value={tableKey(table)}>
                    {table.name}
                  </option>
                ))}
              </optgroup>
            )}
            {viewItems.length > 0 && (
              <optgroup label="View">
                {viewItems.map((table) => (
                  <option key={tableKey(table)} value={tableKey(table)}>
                    {table.name}
                  </option>
                ))}
              </optgroup>
            )}
          </select>
        </div>

        <Button
          variant="outline"
          onClick={() => setColumnsOpen(true)}
          disabled={!selectedTable}
        >
          <Icon name="ri-list-check-3" />
          Cột ({selectedColumns.length}/{selectedTable?.columns.length ?? 0})
        </Button>

        <div>
          <label
            htmlFor="admin-db-browse-order"
            className="mb-1 block text-xs font-medium text-muted-foreground"
          >
            Sắp xếp theo
          </label>
          <select
            id="admin-db-browse-order"
            aria-label="Sắp xếp theo"
            value={orderBy ?? ""}
            onChange={(event) => handleOrderByChange(event.target.value)}
            disabled={!selectedTable}
            className="h-10 rounded-full border border-border bg-surface px-3 text-sm text-foreground shadow-xs outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30 disabled:cursor-not-allowed disabled:opacity-55"
          >
            <option value="">Mặc định (khóa chính)</option>
            {selectedTable?.columns.map((column) => (
              <option key={column.name} value={column.name}>
                {column.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label
            htmlFor="admin-db-browse-dir"
            className="mb-1 block text-xs font-medium text-muted-foreground"
          >
            Chiều sắp xếp
          </label>
          <select
            id="admin-db-browse-dir"
            aria-label="Chiều sắp xếp"
            value={orderDir}
            onChange={(event) => handleOrderDirChange(event.target.value)}
            disabled={!selectedTable}
            className="h-10 rounded-full border border-border bg-surface px-3 text-sm text-foreground shadow-xs outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30 disabled:cursor-not-allowed disabled:opacity-55"
          >
            <option value="asc">Tăng dần</option>
            <option value="desc">Giảm dần</option>
          </select>
        </div>

        <div>
          <label
            htmlFor="admin-db-browse-limit"
            className="mb-1 block text-xs font-medium text-muted-foreground"
          >
            Số dòng/trang
          </label>
          <select
            id="admin-db-browse-limit"
            aria-label="Số dòng mỗi trang"
            value={limit}
            onChange={(event) => handleLimitChange(Number(event.target.value))}
            disabled={!selectedTable}
            className="h-10 rounded-full border border-border bg-surface px-3 text-sm text-foreground shadow-xs outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30 disabled:cursor-not-allowed disabled:opacity-55"
          >
            {PAGE_SIZES.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </div>
      </div>

      {selectedTable && (
        <div className="space-y-2 rounded-[14px] border border-[#eeeee9] bg-[#fafaf7] p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs font-semibold">Bộ lọc</p>
            <Button
              variant="outline"
              size="xs"
              onClick={handleAddFilter}
              disabled={filters.length >= 10}
            >
              <Icon name="ri-add-line" />
              Thêm bộ lọc
            </Button>
          </div>
          {filters.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              Chưa có bộ lọc. Thêm bộ lọc để thu hẹp dữ liệu.
            </p>
          ) : (
            <div className="space-y-2">
              {filters.map((filter) => (
                <div
                  key={filter.id}
                  className="flex flex-wrap items-center gap-2"
                >
                  <select
                    aria-label="Cột lọc"
                    value={filter.column}
                    onChange={(event) =>
                      handleUpdateFilter(filter.id, {
                        column: event.target.value,
                        operator: "eq",
                        value: "",
                      })
                    }
                    className="h-9 rounded-full border border-border bg-white px-3 text-xs text-foreground shadow-xs outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
                  >
                    {selectedTable.columns.map((column) => (
                      <option key={column.name} value={column.name}>
                        {column.name}
                      </option>
                    ))}
                  </select>
                  <select
                    aria-label="Toán tử lọc"
                    value={filter.operator}
                    onChange={(event) => {
                      const operator = event.target
                        .value as AdminDbFilterOperator;
                      handleUpdateFilter(filter.id, {
                        operator,
                        value: NULL_OPERATORS.has(operator)
                          ? ""
                          : filter.value,
                      });
                    }}
                    className="h-9 rounded-full border border-border bg-white px-3 text-xs text-foreground shadow-xs outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
                  >
                    {FILTER_OPERATORS.map((operator) => (
                      <option key={operator.value} value={operator.value}>
                        {operator.label}
                      </option>
                    ))}
                  </select>
                  {!NULL_OPERATORS.has(filter.operator) && (
                    <Input
                      aria-label="Giá trị lọc"
                      value={filter.value}
                      onChange={(event) =>
                        handleUpdateFilter(filter.id, {
                          value: event.target.value,
                        })
                      }
                      placeholder="Giá trị..."
                      className="h-9 min-w-[160px] flex-1 rounded-full border-border bg-white shadow-none"
                    />
                  )}
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    onClick={() => handleRemoveFilter(filter.id)}
                    aria-label="Xóa bộ lọc"
                  >
                    <Icon name="ri-close-line" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {!selectedTable ? (
        <EmptyState
          icon="ri-table-line"
          title="Chọn bảng để duyệt dữ liệu"
          description="Chọn một bảng hoặc view ở phía trên."
          className="border-0 shadow-none"
        />
      ) : selectedColumns.length === 0 ? (
        <EmptyState
          icon="ri-list-check-3"
          title="Chưa chọn cột"
          description="Mở dialog Cột để chọn ít nhất một cột."
          className="border-0 shadow-none"
        />
      ) : browseQuery.isLoading ? (
        <div className="flex min-h-[220px] flex-col items-center justify-center gap-3 text-muted-foreground">
          <Spinner className="size-6" />
          <p className="text-sm">Đang tải dữ liệu...</p>
        </div>
      ) : browseError ? (
        <QueryErrorPanel error={browseError} />
      ) : result && result.rows.length === 0 ? (
        <EmptyState
          icon="ri-inbox-line"
          title="Không có dữ liệu phù hợp"
          description="Thử bỏ bớt bộ lọc hoặc chọn bảng khác."
          className="border-0 shadow-none"
        />
      ) : result ? (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <Badge variant="success">{result.rowCount} dòng</Badge>
            <span>{formatDuration(result.durationMs)}</span>
            <span>· Trang {page}</span>
            {browseQuery.isFetching && <Spinner className="size-3.5" />}
            <div className="ml-auto flex items-center gap-2">
              <Button
                variant="outline"
                size="xs"
                onClick={() => setOffset((prev) => Math.max(0, prev - limit))}
                disabled={offset === 0 || browseQuery.isFetching}
              >
                <Icon name="ri-arrow-left-s-line" />
                Trước
              </Button>
              <Button
                variant="outline"
                size="xs"
                onClick={() => setOffset((prev) => prev + limit)}
                disabled={!result.hasMore || browseQuery.isFetching}
              >
                Sau
                <Icon name="ri-arrow-right-s-line" />
              </Button>
            </div>
          </div>

          <DataTable
            columns={result.columns}
            rows={result.rows}
            caption="Dữ liệu bảng"
          />

          {!result.hasMore && (
            <p className="text-center text-[11px] text-muted-foreground">
              Đã hết dữ liệu.
            </p>
          )}
        </div>
      ) : null}

      <Dialog open={columnsOpen} onOpenChange={setColumnsOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Chọn cột hiển thị</DialogTitle>
            <DialogDescription>
              {selectedTable
                ? `${selectedTable.name} · ${selectedTable.columns.length} cột`
                : ""}
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-[50vh] overflow-y-auto px-6">
            <div className="mb-2 flex items-center gap-2">
              <Button
                variant="outline"
                size="xs"
                onClick={handleSelectAllColumns}
              >
                Chọn tất cả
              </Button>
              <Button variant="ghost" size="xs" onClick={handleClearColumns}>
                Bỏ chọn tất cả
              </Button>
            </div>
            <div className="space-y-1">
              {selectedTable?.columns.map((column) => (
                <label
                  key={column.name}
                  className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-muted/60"
                >
                  <input
                    type="checkbox"
                    checked={selectedColumns.includes(column.name)}
                    onChange={() => handleToggleColumn(column.name)}
                    className="size-4 rounded border-border"
                  />
                  <span className="font-mono text-xs">{column.name}</span>
                  <span className="ml-auto font-mono text-[10px] text-muted-foreground">
                    {shortTypeLabel(column.type)}
                  </span>
                </label>
              ))}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setColumnsOpen(false)}>
              Hủy
            </Button>
            <Button
              onClick={() => setColumnsOpen(false)}
              disabled={selectedColumns.length === 0}
            >
              Xong
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
