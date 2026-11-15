import { apiFetch } from "./client";

type AdminDbTableKind =
  | "table"
  | "partitioned_table"
  | "view"
  | "materialized_view"
  | "foreign_table";

interface AdminDbColumn {
  name: string;
  type: string;
  nullable: boolean;
  primaryKey: boolean;
  default?: string | null;
}

export interface AdminDbTable {
  schema: string;
  name: string;
  kind: AdminDbTableKind;
  rowEstimate: number | null;
  columns: AdminDbColumn[];
}

export interface AdminDbSchema {
  tables: AdminDbTable[];
  generatedAt: string;
}

export interface AdminDbResultColumn {
  name: string;
  type: string;
}

export interface AdminDbQueryResult {
  columns: AdminDbResultColumn[];
  rows: unknown[][];
  rowCount: number;
  truncated: boolean;
  durationMs: number;
  limit: number;
}

export interface AdminDbQueryErrorDetail {
  code?: string;
  message?: string;
  detail?: string;
  hint?: string | null;
  position?: number | null;
}

export type AdminDbFilterOperator =
  | "eq"
  | "neq"
  | "gt"
  | "gte"
  | "lt"
  | "lte"
  | "contains"
  | "starts_with"
  | "ends_with"
  | "is_null"
  | "is_not_null";

export interface AdminDbFilter {
  column: string;
  operator: AdminDbFilterOperator;
  value?: string | null;
}

export interface AdminDbTableRowsParams {
  schema: string;
  table: string;
  columns: string[];
  limit: number;
  offset: number;
  orderBy?: string | null;
  orderDir: "asc" | "desc";
  filters: AdminDbFilter[];
}

export interface AdminDbTableRowsResult {
  columns: AdminDbResultColumn[];
  rows: unknown[][];
  rowCount: number;
  limit: number;
  offset: number;
  hasMore: boolean;
  durationMs: number;
}

export function fetchAdminDbSchema(refresh = false): Promise<AdminDbSchema> {
  return apiFetch<AdminDbSchema>("/api/admin/db/schema", {
    params: { refresh },
  });
}

export function runAdminDbQuery(
  payload: { sql: string; maxRows: number },
  signal?: AbortSignal,
): Promise<AdminDbQueryResult> {
  return apiFetch<AdminDbQueryResult>("/api/admin/db/query", {
    method: "POST",
    body: payload,
    signal,
    timeoutMs: 20_000,
  });
}

export function fetchAdminDbTableRows(
  params: AdminDbTableRowsParams,
): Promise<AdminDbTableRowsResult> {
  return apiFetch<AdminDbTableRowsResult>(
    `/api/admin/db/tables/${encodeURIComponent(params.table)}/rows`,
    {
      method: "POST",
      body: {
        schema: params.schema,
        columns: params.columns,
        limit: params.limit,
        offset: params.offset,
        orderBy: params.orderBy,
        orderDir: params.orderDir,
        filters: params.filters,
      },
      timeoutMs: 20_000,
    },
  );
}
