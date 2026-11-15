"use client";

import { useEffect, useMemo, useReducer } from "react";
import type {
  AdminDbFilter,
  AdminDbTable,
  AdminDbTableRowsParams,
} from "@/lib/api/admin-db";
import {
  MAX_FILTERS,
  buildTableRowsParams,
  createTableBrowserState,
  newFilter,
  pageNumber,
  partitionTables,
  tableBrowserReducer,
  tableKey,
  toActiveFilters,
  type FilterRow,
} from "./table-browser-state";

export function useTableBrowser(tables: AdminDbTable[]) {
  const [state, dispatch] = useReducer(
    tableBrowserReducer,
    undefined,
    createTableBrowserState,
  );

  const selectedTable = useMemo(
    () => tables.find((table) => tableKey(table) === state.selectedKey) ?? null,
    [tables, state.selectedKey],
  );

  useEffect(() => {
    const timeout = window.setTimeout(
      () => dispatch({ type: "set-debounced-filters", filters: state.filters }),
      400,
    );
    return () => window.clearTimeout(timeout);
  }, [state.filters]);

  const activeFilters = useMemo<AdminDbFilter[]>(
    () => toActiveFilters(state.debouncedFilters),
    [state.debouncedFilters],
  );

  const params = useMemo<AdminDbTableRowsParams | null>(
    () =>
      buildTableRowsParams({
        table: selectedTable,
        columns: state.selectedColumns,
        activeFilters,
        limit: state.limit,
        offset: state.offset,
        orderBy: state.orderBy,
        orderDir: state.orderDir,
      }),
    [
      selectedTable,
      state.selectedColumns,
      state.limit,
      state.offset,
      state.orderBy,
      state.orderDir,
      activeFilters,
    ],
  );

  const { tableItems, viewItems } = useMemo(
    () => partitionTables(tables),
    [tables],
  );

  const selectTable = (key: string) => {
    const table = tables.find((item) => tableKey(item) === key) ?? null;
    dispatch({ type: "select-table", table });
  };

  const toggleColumn = (name: string) => {
    dispatch({ type: "toggle-column", name });
  };

  const selectAllColumns = () => {
    if (!selectedTable) return;
    dispatch({
      type: "select-all-columns",
      columns: selectedTable.columns.map((column) => column.name),
    });
  };

  const clearColumns = () => {
    dispatch({ type: "clear-columns" });
  };

  const addFilter = () => {
    if (!selectedTable || state.filters.length >= MAX_FILTERS) return;
    dispatch({ type: "add-filter", filter: newFilter(selectedTable) });
  };

  const updateFilter = (id: string, patch: Partial<Omit<FilterRow, "id">>) => {
    dispatch({ type: "update-filter", id, patch });
  };

  const removeFilter = (id: string) => {
    dispatch({ type: "remove-filter", id });
  };

  const setOrderBy = (value: string) => {
    dispatch({ type: "set-order-by", value });
  };

  const setOrderDir = (value: string) => {
    dispatch({ type: "set-order-dir", value });
  };

  const setLimit = (value: number) => {
    dispatch({ type: "set-limit", value });
  };

  const goToPreviousPage = () => {
    dispatch({ type: "previous-page" });
  };

  const goToNextPage = () => {
    dispatch({ type: "next-page" });
  };

  const setColumnsOpen = (open: boolean) => {
    dispatch({ type: "set-columns-open", open });
  };

  return {
    selectedKey: state.selectedKey,
    selectedColumns: state.selectedColumns,
    filters: state.filters,
    orderBy: state.orderBy,
    orderDir: state.orderDir,
    limit: state.limit,
    offset: state.offset,
    columnsOpen: state.columnsOpen,
    selectedTable,
    activeFilters,
    params,
    page: pageNumber(state.offset, state.limit),
    tableItems,
    viewItems,
    selectTable,
    toggleColumn,
    selectAllColumns,
    clearColumns,
    addFilter,
    updateFilter,
    removeFilter,
    setOrderBy,
    setOrderDir,
    setLimit,
    goToPreviousPage,
    goToNextPage,
    setColumnsOpen,
  };
}
