import { describe, expect, it } from "vitest";
import type { AdminDbTable } from "@/lib/api/admin-db";
import {
  buildSelectQuery,
  cellToText,
  formatCellValue,
  formatDuration,
  formatRowEstimate,
  isQueryHistoryItem,
  quoteIdent,
  shortTypeLabel,
  toCsv,
  toJson,
  truncateText,
} from "@/lib/admin-db";

const table: AdminDbTable = {
  schema: "public",
  name: "users",
  kind: "table",
  rowEstimate: 120,
  columns: [
    {
      name: "id",
      type: "uuid",
      nullable: false,
      primaryKey: true,
    },
    {
      name: "email",
      type: "text",
      nullable: false,
      primaryKey: false,
    },
  ],
};

describe("admin-db helpers", () => {
  it("quotes identifiers", () => {
    expect(quoteIdent("users")).toBe('"users"');
    expect(quoteIdent('weird"name')).toBe('"weird""name"');
  });

  it("builds a safe SELECT with primary key ordering", () => {
    expect(buildSelectQuery(table, 50)).toBe(
      'SELECT "id", "email"\nFROM "public"."users"\nORDER BY "id"\nLIMIT 50;',
    );
  });

  it("formats row estimates", () => {
    expect(formatRowEstimate(null)).toBe("—");
    expect(formatRowEstimate(0)).toBe("0");
    expect(formatRowEstimate(999)).toBe("999");
    expect(formatRowEstimate(1200)).toBe("~1.2k");
    expect(formatRowEstimate(12000)).toBe("~12k");
    expect(formatRowEstimate(1_500_000)).toBe("~1.5M");
  });

  it("formats durations", () => {
    expect(formatDuration(42)).toBe("42 ms");
    expect(formatDuration(1500)).toBe("1.50 s");
  });

  it("shortens long PostgreSQL type names", () => {
    expect(shortTypeLabel("character varying")).toBe("varchar");
    expect(shortTypeLabel("character varying(255)")).toBe("varchar");
    expect(shortTypeLabel("timestamp with time zone")).toBe("timestamptz");
    expect(shortTypeLabel("timestamp without time zone")).toBe("timestamp");
    expect(shortTypeLabel("double precision")).toBe("float8");
    expect(shortTypeLabel("integer")).toBe("int4");
    expect(shortTypeLabel("time without time zone")).toBe("time");
    expect(shortTypeLabel("text[]")).toBe("text[]");
    expect(shortTypeLabel("integer[]")).toBe("int4[]");
    expect(shortTypeLabel("timestamp with time zone[]")).toBe("timestamptz[]");
    expect(shortTypeLabel("uuid")).toBe("uuid");
  });

  it("formats null, boolean, number, json and text cells", () => {
    expect(formatCellValue(null, "text")).toMatchObject({
      text: "NULL",
      kind: "null",
    });
    expect(formatCellValue(true, "boolean")).toMatchObject({
      text: "true",
      kind: "boolean",
    });
    expect(formatCellValue(42, "integer")).toMatchObject({
      text: "42",
      kind: "number",
    });
    expect(formatCellValue({ a: 1 }, "jsonb")).toMatchObject({
      kind: "json",
    });
    expect(formatCellValue("hello", "text")).toMatchObject({
      text: "hello",
      kind: "text",
    });
  });

  it("formats date and timestamp cells", () => {
    expect(formatCellValue("2026-11-10", "date")).toMatchObject({
      text: "10/11/2026",
      kind: "date",
    });
    expect(
      formatCellValue("2026-11-10T09:12:00+07:00", "timestamp with time zone")
        .kind,
    ).toBe("date");
  });

  it("exports CSV with escaping and BOM", () => {
    const csv = toCsv(
      [
        { name: "name", type: "text" },
        { name: "note", type: "text" },
      ],
      [
        ["Nguyễn A", 'có "ngoặc"'],
        [null, "dòng\nmới"],
      ],
    );
    expect(csv.startsWith("\uFEFF")).toBe(true);
    expect(csv).toContain('"có ""ngoặc"""');
    expect(csv).toContain('"dòng\nmới"');
  });

  it("exports JSON", () => {
    const json = toJson([{ name: "id", type: "uuid" }], [["abc"]]);
    expect(JSON.parse(json)).toEqual({
      columns: [{ name: "id", type: "uuid" }],
      rows: [["abc"]],
    });
  });

  it("converts cells to text", () => {
    expect(cellToText(null)).toBe("NULL");
    expect(cellToText({ a: 1 })).toBe('{\n  "a": 1\n}');
    expect(cellToText("x")).toBe("x");
  });

  it("truncates long text", () => {
    expect(truncateText("abcdef", 3)).toBe("abc…");
    expect(truncateText("abc", 3)).toBe("abc");
  });

  it("validates history items", () => {
    expect(
      isQueryHistoryItem({
        id: "1",
        sql: "SELECT 1",
        ranAt: "2026-11-10T00:00:00Z",
        durationMs: 10,
        rowCount: 1,
        ok: true,
      }),
    ).toBe(true);
    expect(isQueryHistoryItem({ id: "1" })).toBe(false);
  });
});
