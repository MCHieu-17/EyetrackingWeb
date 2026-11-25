"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import type { AdminDbTable } from "@/lib/api/admin-db";
import { formatRowEstimate, shortTypeLabel } from "@/lib/admin-db";
import { cn } from "@/lib/utils";

interface SchemaExplorerProps {
  tables: AdminDbTable[];
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
  onRetry: () => void;
  onSelectTable: (table: AdminDbTable) => void;
  onInsertColumn: (columnName: string) => void;
  onRefresh: () => void;
  className?: string;
}

interface SchemaGroupProps {
  title: string;
  items: AdminDbTable[];
  expanded: Set<string>;
  onToggle: (key: string) => void;
  onSelectTable: (table: AdminDbTable) => void;
  onInsertColumn: (columnName: string) => void;
}

function SchemaGroup({
  title,
  items,
  expanded,
  onToggle,
  onSelectTable,
  onInsertColumn,
}: SchemaGroupProps) {
  if (items.length === 0) return null;

  return (
    <div>
      <p className="px-2 py-1 text-[10px] font-bold uppercase tracking-[0.15em] text-muted-foreground">
        {title} ({items.length})
      </p>
      <div className="space-y-1">
        {items.map((table) => {
          const key = `${table.schema}.${table.name}`;
          const isOpen = expanded.has(key);
          const isView =
            table.kind === "view" || table.kind === "materialized_view";
          return (
            <div
              key={key}
              className="rounded-xl border border-transparent hover:border-border"
            >
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => onToggle(key)}
                  className="flex size-7 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                  aria-label={isOpen ? "Thu gọn bảng" : "Mở rộng bảng"}
                  aria-expanded={isOpen}
                >
                  <Icon
                    name={
                      isOpen ? "ri-arrow-down-s-line" : "ri-arrow-right-s-line"
                    }
                    className="size-4"
                  />
                </button>
                <button
                  type="button"
                  onClick={() => onSelectTable(table)}
                  className="flex min-w-0 flex-1 items-center gap-2 rounded-lg px-1 py-1.5 text-left transition-colors hover:bg-muted/60"
                  title="Tạo câu lệnh SELECT cho bảng này"
                >
                  <Icon
                    name={isView ? "ri-eye-line" : "ri-table-line"}
                    className="size-4 shrink-0 text-muted-foreground"
                  />
                  <span className="truncate font-mono text-xs font-medium">
                    {table.name}
                  </span>
                  <span className="ml-auto shrink-0 rounded-full bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                    {formatRowEstimate(table.rowEstimate)}
                  </span>
                </button>
              </div>

              {isOpen && (
                <div className="ml-8 space-y-0.5 pb-2 pr-2">
                  {table.columns.map((column) => (
                    <button
                      key={column.name}
                      type="button"
                      onClick={() => onInsertColumn(column.name)}
                      className="flex w-full items-center gap-2 rounded-md px-2 py-1 text-left transition-colors hover:bg-muted/60"
                      title="Chèn tên cột vào câu lệnh"
                    >
                      <Icon
                        name={
                          column.primaryKey
                            ? "ri-key-2-line"
                            : "ri-stack-line"
                        }
                        className={cn(
                          "size-3.5 shrink-0",
                          column.primaryKey
                            ? "text-warning"
                            : "text-muted-foreground",
                        )}
                      />
                      <span className="truncate font-mono text-[11px]">
                        {column.name}
                      </span>
                      <span
                        className="ml-auto shrink-0 font-mono text-[10px] text-muted-foreground"
                        title={column.type}
                      >
                        {shortTypeLabel(column.type)}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function SchemaExplorer({
  tables,
  isLoading,
  isError,
  error,
  onRetry,
  onSelectTable,
  onInsertColumn,
  onRefresh,
  className,
}: SchemaExplorerProps) {
  const [query, setQuery] = React.useState("");
  const [expanded, setExpanded] = React.useState<Set<string>>(new Set());

  const normalized = query.trim().toLowerCase();
  const filtered = normalized
    ? tables.filter(
        (table) =>
          table.name.toLowerCase().includes(normalized) ||
          table.columns.some((column) =>
            column.name.toLowerCase().includes(normalized),
          ),
      )
    : tables;

  const tableItems = filtered.filter(
    (table) => table.kind !== "view" && table.kind !== "materialized_view",
  );
  const viewItems = filtered.filter(
    (table) => table.kind === "view" || table.kind === "materialized_view",
  );

  const toggle = (key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return (
    <section
      className={cn(
        "flex max-h-[calc(100vh-220px)] flex-col rounded-[18px] border border-border bg-card shadow-xs",
        className,
      )}
    >
      <div className="border-b border-border p-3 pr-12">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Icon
              name="ri-database-2-line"
              className="size-4 text-muted-foreground"
            />
            <h2 className="text-sm font-semibold">Bảng &amp; cột</h2>
          </div>
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={onRefresh}
            aria-label="Làm mới schema"
            title="Làm mới schema"
          >
            <Icon name="ri-refresh-line" />
          </Button>
        </div>
        <div className="relative mt-3">
          <Icon
            name="ri-search-line"
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Tìm bảng hoặc cột..."
            className="h-9 rounded-full border-transparent bg-muted pl-9 shadow-none focus-visible:border-border"
            aria-label="Tìm bảng hoặc cột"
          />
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {isLoading ? (
          <div className="space-y-2 p-1">
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton key={index} className="h-9 rounded-xl" />
            ))}
          </div>
        ) : isError ? (
          <ErrorState
            title="Không tải được schema"
            description={
              error instanceof Error ? error.message : "Vui lòng thử lại."
            }
            onRetry={onRetry}
            className="border-0 shadow-none"
          />
        ) : filtered.length === 0 ? (
          <EmptyState
            icon="ri-search-line"
            title="Không tìm thấy bảng/cột"
            description="Thử từ khóa khác."
            className="border-0 shadow-none"
          />
        ) : (
          <div className="space-y-3">
            <SchemaGroup
              title="Bảng"
              items={tableItems}
              expanded={expanded}
              onToggle={toggle}
              onSelectTable={onSelectTable}
              onInsertColumn={onInsertColumn}
            />
            <SchemaGroup
              title="View"
              items={viewItems}
              expanded={expanded}
              onToggle={toggle}
              onSelectTable={onSelectTable}
              onInsertColumn={onInsertColumn}
            />
          </div>
        )}
      </div>

      <div className="border-t border-border px-3 py-2 text-[11px] text-muted-foreground">
        {tables.length} bảng/view · Click để tạo SELECT
      </div>
    </section>
  );
}
