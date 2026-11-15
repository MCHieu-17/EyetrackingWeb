import type {
  AdminDbFilter,
  AdminDbFilterOperator,
  AdminDbTable,
  AdminDbTableRowsParams,
} from "@/lib/api/admin-db";

export interface FilterRow {
  id: string;
  column: string;
  operator: AdminDbFilterOperator;
  value: string;
}

export interface TableBrowserState {
  selectedKey: string;
  selectedColumns: string[];
  filters: FilterRow[];
  debouncedFilters: FilterRow[];
  orderBy: string | null;
  orderDir: "asc" | "desc";
  limit: number;
  offset: number;
  columnsOpen: boolean;
}

export type TableBrowserAction =
  | { type: "select-table"; table: AdminDbTable | null }
  | { type: "toggle-column"; name: string }
  | { type: "select-all-columns"; columns: string[] }
  | { type: "clear-columns" }
  | { type: "add-filter"; filter: FilterRow }
  | { type: "update-filter"; id: string; patch: Partial<Omit<FilterRow, "id">> }
  | { type: "remove-filter"; id: string }
  | { type: "set-order-by"; value: string }
  | { type: "set-order-dir"; value: string }
  | { type: "set-limit"; value: number }
  | { type: "previous-page" }
  | { type: "next-page" }
  | { type: "set-columns-open"; open: boolean }
  | { type: "set-debounced-filters"; filters: FilterRow[] };

export const FILTER_OPERATORS: {
  value: AdminDbFilterOperator;
  label: string;
}[] = [
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

export const NULL_OPERATORS = new Set<AdminDbFilterOperator>([
  "is_null",
  "is_not_null",
]);

export const PAGE_SIZES = [50, 100, 200];
export const MAX_FILTERS = 10;
const DEFAULT_PAGE_SIZE = 50;

export function tableKey(table: AdminDbTable): string {
  return `${table.schema}.${table.name}`;
}

export function createTableBrowserState(): TableBrowserState {
  return {
    selectedKey: "",
    selectedColumns: [],
    filters: [],
    debouncedFilters: [],
    orderBy: null,
    orderDir: "asc",
    limit: DEFAULT_PAGE_SIZE,
    offset: 0,
    columnsOpen: false,
  };
}

export function newFilter(
  table: AdminDbTable,
  id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
): FilterRow {
  return {
    id,
    column: table.columns[0]?.name ?? "",
    operator: "eq",
    value: "",
  };
}

export function toActiveFilters(filters: FilterRow[]): AdminDbFilter[] {
  return filters
    .filter(
      (filter) => NULL_OPERATORS.has(filter.operator) || filter.value !== "",
    )
    .map((filter) => ({
      column: filter.column,
      operator: filter.operator,
      value: NULL_OPERATORS.has(filter.operator) ? null : filter.value,
    }));
}

export function buildTableRowsParams({
  table,
  columns,
  activeFilters,
  limit,
  offset,
  orderBy,
  orderDir,
}: {
  table: AdminDbTable | null;
  columns: string[];
  activeFilters: AdminDbFilter[];
  limit: number;
  offset: number;
  orderBy: string | null;
  orderDir: "asc" | "desc";
}): AdminDbTableRowsParams | null {
  if (!table || columns.length === 0) return null;
  return {
    schema: table.schema,
    table: table.name,
    columns,
    limit,
    offset,
    orderBy,
    orderDir,
    filters: activeFilters,
  };
}

export function pageNumber(offset: number, limit: number): number {
  return Math.floor(offset / limit) + 1;
}

export function partitionTables(tables: AdminDbTable[]): {
  tableItems: AdminDbTable[];
  viewItems: AdminDbTable[];
} {
  return {
    tableItems: tables.filter(
      (table) => table.kind !== "view" && table.kind !== "materialized_view",
    ),
    viewItems: tables.filter(
      (table) => table.kind === "view" || table.kind === "materialized_view",
    ),
  };
}

export function tableBrowserReducer(
  state: TableBrowserState,
  action: TableBrowserAction,
): TableBrowserState {
  switch (action.type) {
    case "select-table": {
      const table = action.table;
      return {
        ...state,
        selectedKey: table ? tableKey(table) : "",
        selectedColumns: table
          ? table.columns.map((column) => column.name)
          : [],
        filters: [],
        debouncedFilters: [],
        orderBy: table?.columns.find((column) => column.primaryKey)?.name ?? null,
        orderDir: "asc",
        offset: 0,
      };
    }
    case "toggle-column":
      return {
        ...state,
        selectedColumns: state.selectedColumns.includes(action.name)
          ? state.selectedColumns.filter((item) => item !== action.name)
          : [...state.selectedColumns, action.name],
        offset: 0,
      };
    case "select-all-columns":
      return { ...state, selectedColumns: action.columns, offset: 0 };
    case "clear-columns":
      return { ...state, selectedColumns: [], offset: 0 };
    case "add-filter":
      if (state.filters.length >= MAX_FILTERS) return state;
      return { ...state, filters: [...state.filters, action.filter], offset: 0 };
    case "update-filter":
      return {
        ...state,
        filters: state.filters.map((filter) =>
          filter.id === action.id ? { ...filter, ...action.patch } : filter,
        ),
        offset: 0,
      };
    case "remove-filter":
      return {
        ...state,
        filters: state.filters.filter((filter) => filter.id !== action.id),
        offset: 0,
      };
    case "set-order-by":
      return { ...state, orderBy: action.value || null, offset: 0 };
    case "set-order-dir":
      return {
        ...state,
        orderDir: action.value === "desc" ? "desc" : "asc",
        offset: 0,
      };
    case "set-limit":
      return { ...state, limit: action.value, offset: 0 };
    case "previous-page":
      return {
        ...state,
        offset: Math.max(0, state.offset - state.limit),
      };
    case "next-page":
      return { ...state, offset: state.offset + state.limit };
    case "set-columns-open":
      return { ...state, columnsOpen: action.open };
    case "set-debounced-filters":
      return { ...state, debouncedFilters: action.filters };
  }
}
