"use client";

import {
  keepPreviousData,
  useMutation,
  useQuery,
} from "@tanstack/react-query";
import {
  fetchAdminDbSchema,
  fetchAdminDbTableRows,
  runAdminDbQuery,
  type AdminDbQueryResult,
  type AdminDbTableRowsParams,
} from "@/lib/api/admin-db";
import { queryKeys } from "@/lib/query-keys";

export function useAdminDbSchema() {
  return useQuery({
    queryKey: queryKeys.admin.dbSchema,
    queryFn: () => fetchAdminDbSchema(),
    staleTime: 60_000,
  });
}

export function useRunAdminDbQuery() {
  return useMutation({
    mutationFn: ({
      sql,
      maxRows,
      signal,
    }: {
      sql: string;
      maxRows: number;
      signal?: AbortSignal;
    }): Promise<AdminDbQueryResult> =>
      runAdminDbQuery({ sql, maxRows }, signal),
  });
}

export function useAdminDbTableRows(params: AdminDbTableRowsParams | null) {
  return useQuery({
    queryKey: queryKeys.admin.dbTableRows(params),
    queryFn: () => fetchAdminDbTableRows(params as AdminDbTableRowsParams),
    enabled: params !== null,
    staleTime: 10_000,
    placeholderData: keepPreviousData,
  });
}
