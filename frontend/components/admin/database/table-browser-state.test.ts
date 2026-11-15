import { describe, expect, it } from "vitest";
import type { AdminDbTable } from "@/lib/api/admin-db";
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
  type TableBrowserState,
} from "@/components/admin/database/table-browser-state";

const usersTable: AdminDbTable = {
  schema: "public",
  name: "users",
  kind: "table",
  rowEstimate: 120,
  columns: [
    { name: "id", type: "uuid", nullable: false, primaryKey: true },
    { name: "email", type: "text", nullable: false, primaryKey: false },
    { name: "name", type: "text", nullable: true, primaryKey: false },
  ],
};

const usersView: AdminDbTable = {
  schema: "public",
  name: "active_users",
  kind: "materialized_view",
  rowEstimate: 10,
  columns: [
    { name: "id", type: "uuid", nullable: false, primaryKey: false },
  ],
};

const logsTable: AdminDbTable = {
  schema: "audit",
  name: "logs",
  kind: "partitioned_table",
  rowEstimate: null,
  columns: [
    { name: "created_at", type: "timestamptz", nullable: false, primaryKey: false },
    { name: "message", type: "text", nullable: true, primaryKey: false },
  ],
};

function filter(overrides: Partial<FilterRow> = {}): FilterRow {
  return {
    id: "filter-1",
    column: "email",
    operator: "eq",
    value: "a@example.com",
    ...overrides,
  };
}

function stateWith(
  overrides: Partial<TableBrowserState> = {},
): TableBrowserState {
  return { ...createTableBrowserState(), ...overrides };
}

describe("table browser helpers", () => {
  it("ghép khóa bảng từ schema và tên", () => {
    expect(tableKey(usersTable)).toBe("public.users");
  });

  it("tách bảng và view theo kind", () => {
    expect(partitionTables([usersTable, usersView, logsTable])).toEqual({
      tableItems: [usersTable, logsTable],
      viewItems: [usersView],
    });
  });

  it("tạo bộ lọc mới với cột đầu tiên", () => {
    expect(newFilter(usersTable, "filter-1")).toEqual({
      id: "filter-1",
      column: "id",
      operator: "eq",
      value: "",
    });
  });

  it("tạo bộ lọc rỗng khi bảng không có cột", () => {
    expect(newFilter({ ...usersTable, columns: [] }, "filter-2")).toMatchObject({
      id: "filter-2",
      column: "",
      operator: "eq",
      value: "",
    });
  });

  it("bỏ bộ lọc chưa có giá trị", () => {
    expect(
      toActiveFilters([
        filter({ id: "1", value: "a@example.com" }),
        filter({ id: "2", value: "" }),
      ]),
    ).toEqual([
      { column: "email", operator: "eq", value: "a@example.com" },
    ]);
  });

  it("giữ toán tử NULL với value null", () => {
    expect(
      toActiveFilters([
        filter({ id: "1", operator: "is_null", value: "" }),
        filter({ id: "2", operator: "is_not_null", value: "bỏ qua" }),
      ]),
    ).toEqual([
      { column: "email", operator: "is_null", value: null },
      { column: "email", operator: "is_not_null", value: null },
    ]);
  });

  it("tạo params rỗng khi chưa chọn bảng hoặc cột", () => {
    const base = {
      columns: ["id"],
      activeFilters: [],
      limit: 50,
      offset: 0,
      orderBy: "id",
      orderDir: "asc" as const,
    };

    expect(buildTableRowsParams({ ...base, table: null })).toBeNull();
    expect(
      buildTableRowsParams({ ...base, table: usersTable, columns: [] }),
    ).toBeNull();
  });

  it("tạo params duyệt bảng đúng hợp đồng API", () => {
    expect(
      buildTableRowsParams({
        table: usersTable,
        columns: ["id", "email"],
        activeFilters: [{ column: "email", operator: "contains", value: "a" }],
        limit: 100,
        offset: 200,
        orderBy: "email",
        orderDir: "desc",
      }),
    ).toEqual({
      schema: "public",
      table: "users",
      columns: ["id", "email"],
      limit: 100,
      offset: 200,
      orderBy: "email",
      orderDir: "desc",
      filters: [{ column: "email", operator: "contains", value: "a" }],
    });
  });

  it("tính số trang từ offset và limit", () => {
    expect(pageNumber(0, 50)).toBe(1);
    expect(pageNumber(50, 50)).toBe(2);
    expect(pageNumber(250, 100)).toBe(3);
  });
});

describe("tableBrowserReducer", () => {
  it("khởi tạo trạng thái mặc định", () => {
    expect(createTableBrowserState()).toEqual({
      selectedKey: "",
      selectedColumns: [],
      filters: [],
      debouncedFilters: [],
      orderBy: null,
      orderDir: "asc",
      limit: 50,
      offset: 0,
      columnsOpen: false,
    });
  });

  it("chọn bảng: chọn mọi cột, khóa chính và đặt lại bộ lọc/phân trang", () => {
    const previous = stateWith({
      selectedKey: "audit.logs",
      selectedColumns: ["message"],
      filters: [filter()],
      debouncedFilters: [filter()],
      orderBy: "message",
      orderDir: "desc",
      limit: 200,
      offset: 400,
    });

    const next = tableBrowserReducer(previous, {
      type: "select-table",
      table: usersTable,
    });

    expect(next).toMatchObject({
      selectedKey: "public.users",
      selectedColumns: ["id", "email", "name"],
      filters: [],
      debouncedFilters: [],
      orderBy: "id",
      orderDir: "asc",
      limit: 200,
      offset: 0,
    });
  });

  it("bỏ chọn bảng khi chọn option rỗng", () => {
    const next = tableBrowserReducer(
      stateWith({ selectedKey: "public.users", selectedColumns: ["id"] }),
      { type: "select-table", table: null },
    );

    expect(next).toMatchObject({
      selectedKey: "",
      selectedColumns: [],
      orderBy: null,
      offset: 0,
    });
  });

  it("bật/tắt một cột và đặt lại offset", () => {
    const next = tableBrowserReducer(
      stateWith({ selectedColumns: ["id"], offset: 100 }),
      { type: "toggle-column", name: "email" },
    );
    expect(next.selectedColumns).toEqual(["id", "email"]);
    expect(next.offset).toBe(0);

    const removed = tableBrowserReducer(next, {
      type: "toggle-column",
      name: "id",
    });
    expect(removed.selectedColumns).toEqual(["email"]);
  });

  it("chọn tất cả và bỏ chọn tất cả cột", () => {
    const all = tableBrowserReducer(stateWith({ offset: 50 }), {
      type: "select-all-columns",
      columns: ["id", "email", "name"],
    });
    expect(all).toMatchObject({
      selectedColumns: ["id", "email", "name"],
      offset: 0,
    });

    const none = tableBrowserReducer(all, { type: "clear-columns" });
    expect(none.selectedColumns).toEqual([]);
  });

  it("thêm bộ lọc và giới hạn tối đa", () => {
    const next = tableBrowserReducer(stateWith({ offset: 100 }), {
      type: "add-filter",
      filter: filter(),
    });
    expect(next.filters).toEqual([filter()]);
    expect(next.offset).toBe(0);

    const full = stateWith({
      filters: Array.from({ length: MAX_FILTERS }, (_, index) =>
        filter({ id: `filter-${index}` }),
      ),
    });
    expect(
      tableBrowserReducer(full, {
        type: "add-filter",
        filter: filter({ id: "overflow" }),
      }),
    ).toBe(full);
  });

  it("cập nhật và xóa bộ lọc theo id", () => {
    const initial = stateWith({
      filters: [filter({ id: "1" }), filter({ id: "2", value: "b" })],
      offset: 100,
    });

    const updated = tableBrowserReducer(initial, {
      type: "update-filter",
      id: "1",
      patch: { operator: "contains", value: "abc" },
    });
    expect(updated.filters[0]).toMatchObject({
      operator: "contains",
      value: "abc",
    });
    expect(updated.offset).toBe(0);

    const removed = tableBrowserReducer(updated, {
      type: "remove-filter",
      id: "1",
    });
    expect(removed.filters).toEqual([filter({ id: "2", value: "b" })]);
  });

  it("đổi sắp xếp và kích thước trang", () => {
    const ordered = tableBrowserReducer(stateWith({ offset: 50 }), {
      type: "set-order-by",
      value: "email",
    });
    expect(ordered).toMatchObject({ orderBy: "email", offset: 0 });

    const cleared = tableBrowserReducer(ordered, {
      type: "set-order-by",
      value: "",
    });
    expect(cleared.orderBy).toBeNull();

    expect(
      tableBrowserReducer(cleared, {
        type: "set-order-dir",
        value: "desc",
      }).orderDir,
    ).toBe("desc");
    expect(
      tableBrowserReducer(cleared, {
        type: "set-order-dir",
        value: "khác",
      }).orderDir,
    ).toBe("asc");

    const resized = tableBrowserReducer(cleared, {
      type: "set-limit",
      value: 200,
    });
    expect(resized).toMatchObject({ limit: 200, offset: 0 });
  });

  it("chuyển trang trước/sau theo limit và không xuống dưới 0", () => {
    expect(
      tableBrowserReducer(stateWith({ offset: 100, limit: 50 }), {
        type: "previous-page",
      }).offset,
    ).toBe(50);
    expect(
      tableBrowserReducer(stateWith({ offset: 0, limit: 50 }), {
        type: "previous-page",
      }).offset,
    ).toBe(0);
    expect(
      tableBrowserReducer(stateWith({ offset: 100, limit: 50 }), {
        type: "next-page",
      }).offset,
    ).toBe(150);
  });

  it("cập nhật bộ lọc debounce mà không đổi offset", () => {
    const filters = [filter()];
    const debounced = tableBrowserReducer(stateWith({ offset: 100 }), {
      type: "set-debounced-filters",
      filters,
    });
    expect(debounced.debouncedFilters).toEqual(filters);
    expect(debounced.offset).toBe(100);
  });

  it("mở/đóng dialog chọn cột", () => {
    expect(
      tableBrowserReducer(stateWith(), { type: "set-columns-open", open: true })
        .columnsOpen,
    ).toBe(true);
  });
});
