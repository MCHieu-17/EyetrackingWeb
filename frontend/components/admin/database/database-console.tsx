"use client";

import * as React from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { useAdminDbSchema, useRunAdminDbQuery } from "@/hooks/use-admin-db";
import type { AdminDbQueryResult, AdminDbTable } from "@/lib/api/admin-db";
import { ApiError } from "@/lib/api/client";
import {
  buildSelectQuery,
  copyText,
  downloadFile,
  exportFilename,
  isQueryHistoryItem,
  quoteIdent,
  toCsv,
  toJson,
  type ExampleQuery,
  type QueryHistoryItem,
} from "@/lib/admin-db";
import { cn } from "@/lib/utils";
import { ExampleQueries } from "./example-queries";
import { QueryEditor } from "./query-editor";
import { QueryHistory } from "./query-history";
import { ResultTable } from "./result-table";
import { SchemaExplorer } from "./schema-explorer";
import { TableBrowser } from "./table-browser";

const HISTORY_KEY = "eyelearning.admin.db.history.v1";
const LAST_SQL_KEY = "eyelearning.admin.db.last-sql.v1";
const MAX_HISTORY = 20;

const DEFAULT_SQL = `SELECT u.id, u.email, u.full_name, u.role, u.status, u.created_at
FROM users u
ORDER BY u.created_at DESC
LIMIT 100;`;

function loadHistory(): QueryHistoryItem[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(HISTORY_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isQueryHistoryItem).slice(0, MAX_HISTORY);
  } catch {
    return [];
  }
}

function saveHistory(items: QueryHistoryItem[]): void {
  try {
    window.localStorage.setItem(HISTORY_KEY, JSON.stringify(items));
  } catch {
    /* Storage có thể bị chặn. */
  }
}

function loadLastSql(): string {
  if (typeof window === "undefined") return DEFAULT_SQL;
  try {
    return window.localStorage.getItem(LAST_SQL_KEY) || DEFAULT_SQL;
  } catch {
    return DEFAULT_SQL;
  }
}

function saveLastSql(sql: string): void {
  try {
    window.localStorage.setItem(LAST_SQL_KEY, sql);
  } catch {
    /* Storage có thể bị chặn. */
  }
}

type TabId = "results" | "browse" | "history" | "examples";

export function DatabaseConsole() {
  const schemaQuery = useAdminDbSchema();
  const runMutation = useRunAdminDbQuery();

  const [sql, setSql] = React.useState(DEFAULT_SQL);
  const [maxRows, setMaxRows] = React.useState(100);
  const [result, setResult] = React.useState<AdminDbQueryResult | null>(null);
  const [error, setError] = React.useState<ApiError | null>(null);
  const [activeTab, setActiveTab] = React.useState<TabId>("results");
  const [history, setHistory] = React.useState<QueryHistoryItem[]>([]);
  const [notice, setNotice] = React.useState<string | null>(null);
  const [isRunning, setIsRunning] = React.useState(false);
  const [mobileSchemaOpen, setMobileSchemaOpen] = React.useState(false);
  const abortRef = React.useRef<AbortController | null>(null);
  const editorRef = React.useRef<HTMLTextAreaElement | null>(null);

  React.useEffect(() => {
    // Đọc localStorage sau khi mount để tránh hydration mismatch.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setHistory(loadHistory());
    setSql(loadLastSql());
  }, []);

  React.useEffect(() => {
    return () => {
      abortRef.current?.abort();
      abortRef.current = null;
    };
  }, []);

  React.useEffect(() => {
    if (!notice) return;
    const timeout = window.setTimeout(() => setNotice(null), 3000);
    return () => window.clearTimeout(timeout);
  }, [notice]);

  const addHistory = React.useCallback(
    (item: Omit<QueryHistoryItem, "id">) => {
      setHistory((prev) => {
        const next = [
          {
            ...item,
            id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          },
          ...prev,
        ].slice(0, MAX_HISTORY);
        saveHistory(next);
        return next;
      });
    },
    [],
  );

  const runQuery = React.useCallback(async () => {
    const trimmed = sql.trim();
    if (!trimmed) {
      setError(new ApiError(400, "Vui lòng nhập câu lệnh SQL."));
      setResult(null);
      setActiveTab("results");
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setIsRunning(true);
    setError(null);
    setActiveTab("results");
    const startedAt = Date.now();

    try {
      const data = await runMutation.mutateAsync({
        sql: trimmed,
        maxRows,
        signal: controller.signal,
      });
      setResult(data);
      addHistory({
        sql: trimmed,
        ranAt: new Date().toISOString(),
        durationMs: data.durationMs,
        rowCount: data.rowCount,
        ok: true,
      });
      saveLastSql(trimmed);
    } catch (err) {
      if (controller.signal.aborted) return;
      const apiError =
        err instanceof ApiError
          ? err
          : new ApiError(
              0,
              err instanceof Error ? err.message : "Không chạy được truy vấn.",
            );
      setError(apiError);
      setResult(null);
      addHistory({
        sql: trimmed,
        ranAt: new Date().toISOString(),
        durationMs: Date.now() - startedAt,
        rowCount: 0,
        ok: false,
        error: apiError.message,
      });
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
        setIsRunning(false);
      }
    }
  }, [sql, maxRows, runMutation, addHistory]);

  const cancelQuery = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsRunning(false);
  };

  const handleSelectTable = (table: AdminDbTable) => {
    setSql(buildSelectQuery(table, maxRows));
    setActiveTab("results");
    setMobileSchemaOpen(false);
    requestAnimationFrame(() => editorRef.current?.focus());
  };

  const handleInsertColumn = (columnName: string) => {
    const token = quoteIdent(columnName);
    const textarea = editorRef.current;
    if (!textarea) {
      setSql(
        (prev) =>
          `${prev}${prev.endsWith(" ") || prev.endsWith("\n") ? "" : " "}${token}`,
      );
      return;
    }
    const start = textarea.selectionStart ?? sql.length;
    const end = textarea.selectionEnd ?? sql.length;
    const next = `${sql.slice(0, start)}${token}${sql.slice(end)}`;
    setSql(next);
    requestAnimationFrame(() => {
      textarea.focus();
      const cursor = start + token.length;
      textarea.setSelectionRange(cursor, cursor);
    });
  };

  const handleSelectExample = (example: ExampleQuery) => {
    setSql(example.sql);
    setActiveTab("results");
    requestAnimationFrame(() => editorRef.current?.focus());
  };

  const handleSelectHistory = (item: QueryHistoryItem) => {
    setSql(item.sql);
    setActiveTab("results");
    requestAnimationFrame(() => editorRef.current?.focus());
  };

  const handleClearHistory = () => {
    setHistory([]);
    try {
      window.localStorage.removeItem(HISTORY_KEY);
    } catch {
      /* ignore */
    }
  };

  const handleExportCsv = () => {
    if (!result) return;
    downloadFile(
      exportFilename("csv"),
      toCsv(result.columns, result.rows),
      "text/csv;charset=utf-8",
    );
  };

  const handleExportJson = () => {
    if (!result) return;
    downloadFile(
      exportFilename("json"),
      toJson(result.columns, result.rows),
      "application/json;charset=utf-8",
    );
  };

  const handleCopyResult = async () => {
    if (!result) return;
    const ok = await copyText(toCsv(result.columns, result.rows));
    setNotice(
      ok ? "Đã sao chép kết quả." : "Không sao chép được. Vui lòng thử lại.",
    );
  };

  const tables = schemaQuery.data?.tables ?? [];
  const schemaError =
    schemaQuery.error instanceof Error ? schemaQuery.error : null;
  const tabs = [
    { id: "results", label: "Kết quả", icon: "ri-table-line" },
    { id: "browse", label: "Duyệt bảng", icon: "ri-list-check-3" },
    { id: "history", label: "Lịch sử", icon: "ri-history-line" },
    { id: "examples", label: "Ví dụ", icon: "ri-code-line" },
  ] as const;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2 rounded-[18px] border border-border bg-card px-4 py-3 text-xs text-muted-foreground shadow-xs">
        <span className="flex items-center gap-1.5 font-medium text-foreground">
          <Icon name="ri-lock-line" className="size-4 text-success" />
          Chế độ chỉ đọc
        </span>
        <span className="text-border">·</span>
        <span>Tối đa 500 dòng</span>
        <span className="text-border">·</span>
        <span>Timeout 10 giây</span>
        <span className="text-border">·</span>
        <span>Truy vấn được ghi log</span>
      </div>

      {notice && <Alert variant="success" title={notice} />}

      <div className="grid gap-5 lg:grid-cols-[300px_minmax(0,1fr)]">
        <aside className="hidden lg:block">
          <div className="lg:sticky lg:top-24">
            <SchemaExplorer
              tables={tables}
              isLoading={schemaQuery.isLoading}
              isError={schemaQuery.isError}
              error={schemaError}
              onRetry={() => void schemaQuery.refetch()}
              onSelectTable={handleSelectTable}
              onInsertColumn={handleInsertColumn}
              onRefresh={() => void schemaQuery.refetch()}
            />
          </div>
        </aside>

        <div className="space-y-5">
          <div className="flex items-center justify-between gap-3 lg:hidden">
            <Button
              variant="outline"
              onClick={() => setMobileSchemaOpen(true)}
            >
              <Icon name="ri-table-line" />
              Bảng &amp; cột
            </Button>
            <span className="text-xs text-muted-foreground">
              {tables.length} bảng/view
            </span>
          </div>

          <QueryEditor
            value={sql}
            onChange={setSql}
            onRun={() => void runQuery()}
            onCancel={cancelQuery}
            isRunning={isRunning}
            maxRows={maxRows}
            onMaxRowsChange={setMaxRows}
            textareaRef={editorRef}
          />

          <section className="rounded-[18px] border border-border bg-card shadow-xs">
            <div
              role="tablist"
              aria-label="Khu vực kết quả"
              className="flex flex-wrap items-center gap-1 border-b border-border p-2"
            >
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  id={`admin-db-tab-${tab.id}`}
                  aria-selected={activeTab === tab.id}
                  aria-controls={`admin-db-panel-${tab.id}`}
                  tabIndex={activeTab === tab.id ? 0 : -1}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    "flex h-9 items-center gap-2 rounded-full px-3 text-sm font-medium transition-colors",
                    activeTab === tab.id
                      ? "bg-sidebar-accent text-sidebar-accent-foreground shadow-sm"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground",
                  )}
                >
                  <Icon name={tab.icon} className="size-4" />
                  {tab.label}
                  {tab.id === "history" && history.length > 0 && (
                    <span className="rounded-full bg-muted px-1.5 py-0.5 font-mono text-[10px]">
                      {history.length}
                    </span>
                  )}
                </button>
              ))}
            </div>

            <div
              id="admin-db-panel-results"
              role="tabpanel"
              aria-labelledby="admin-db-tab-results"
              hidden={activeTab !== "results"}
              className="p-4"
            >
              <ResultTable
                result={result}
                error={error}
                isRunning={isRunning}
                onExportCsv={handleExportCsv}
                onExportJson={handleExportJson}
                onCopy={() => void handleCopyResult()}
              />
            </div>
            <div
              id="admin-db-panel-browse"
              role="tabpanel"
              aria-labelledby="admin-db-tab-browse"
              hidden={activeTab !== "browse"}
              className="p-4"
            >
              <TableBrowser
                tables={tables}
                isLoading={schemaQuery.isLoading}
                isError={schemaQuery.isError}
                error={schemaError}
                onRetry={() => void schemaQuery.refetch()}
              />
            </div>
            <div
              id="admin-db-panel-history"
              role="tabpanel"
              aria-labelledby="admin-db-tab-history"
              hidden={activeTab !== "history"}
              className="p-4"
            >
              <QueryHistory
                items={history}
                onSelect={handleSelectHistory}
                onClear={handleClearHistory}
              />
            </div>
            <div
              id="admin-db-panel-examples"
              role="tabpanel"
              aria-labelledby="admin-db-tab-examples"
              hidden={activeTab !== "examples"}
              className="p-4"
            >
              <ExampleQueries onSelect={handleSelectExample} />
            </div>
          </section>
        </div>
      </div>

      <Sheet open={mobileSchemaOpen} onOpenChange={setMobileSchemaOpen}>
        <SheetContent
          side="left"
          className="max-w-sm border-none bg-background p-0"
        >
          <SheetTitle className="sr-only">Bảng &amp; cột</SheetTitle>
          <SchemaExplorer
            tables={tables}
            isLoading={schemaQuery.isLoading}
            isError={schemaQuery.isError}
            error={schemaError}
            onRetry={() => void schemaQuery.refetch()}
            onSelectTable={handleSelectTable}
            onInsertColumn={handleInsertColumn}
            onRefresh={() => void schemaQuery.refetch()}
            className="h-full max-h-none rounded-none border-0 shadow-none"
          />
        </SheetContent>
      </Sheet>
    </div>
  );
}
