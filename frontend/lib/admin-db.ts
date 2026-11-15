import type {
  AdminDbResultColumn,
  AdminDbTable,
} from "@/lib/api/admin-db";

export interface QueryHistoryItem {
  id: string;
  sql: string;
  ranAt: string;
  durationMs: number;
  rowCount: number;
  ok: boolean;
  error?: string;
}

export interface ExampleQuery {
  id: string;
  title: string;
  description: string;
  sql: string;
}

type CellKind = "null" | "boolean" | "number" | "json" | "date" | "text";

export interface FormattedCell {
  text: string;
  kind: CellKind;
  fullText: string;
}

const DATE_TYPES = new Set([
  "date",
  "timestamp",
  "timestamptz",
  "timestamp with time zone",
  "timestamp without time zone",
  "time",
  "timetz",
  "time with time zone",
  "time without time zone",
]);

const ISO_DATE_RE =
  /^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?)?$/;

export function quoteIdent(name: string): string {
  return `"${name.replace(/"/g, '""')}"`;
}

export function buildSelectQuery(table: AdminDbTable, limit = 100): string {
  const columns =
    table.columns.length > 0
      ? table.columns.map((column) => quoteIdent(column.name)).join(", ")
      : "*";
  const primaryKeys = table.columns.filter((column) => column.primaryKey);
  const orderBy =
    primaryKeys.length > 0
      ? `\nORDER BY ${primaryKeys
          .map((column) => quoteIdent(column.name))
          .join(", ")}`
      : "";
  return `SELECT ${columns}\nFROM ${quoteIdent(table.schema)}.${quoteIdent(
    table.name,
  )}${orderBy}\nLIMIT ${limit};`;
}

export function formatRowEstimate(value: number | null): string {
  if (value === null || value === undefined) return "—";
  if (value < 1000) return String(value);
  if (value < 1_000_000) {
    const thousands = value / 1000;
    return `~${thousands >= 10 ? Math.round(thousands) : thousands.toFixed(1)}k`;
  }
  return `~${(value / 1_000_000).toFixed(1)}M`;
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

const TYPE_LABELS: Record<string, string> = {
  "character varying": "varchar",
  "timestamp with time zone": "timestamptz",
  "timestamp without time zone": "timestamp",
  "time with time zone": "timetz",
  "time without time zone": "time",
  "double precision": "float8",
  character: "char",
  "bit varying": "varbit",
  integer: "int4",
  bigint: "int8",
  smallint: "int2",
  boolean: "bool",
  real: "float4",
};

export function shortTypeLabel(type: string): string {
  const normalized = type.toLowerCase();
  const isArray = normalized.endsWith("[]");
  const base = isArray ? normalized.slice(0, -2) : normalized;
  let label = TYPE_LABELS[base] ?? base;
  if (base.startsWith("character varying")) label = "varchar";
  else if (base.startsWith("character(")) label = "char";
  else if (base.startsWith("bit varying")) label = "varbit";
  else if (base.includes("timestamp") && base.includes("with time zone")) {
    label = "timestamptz";
  } else if (base.includes("timestamp")) {
    label = "timestamp";
  } else if (base.includes("time") && base.includes("with time zone")) {
    label = "timetz";
  } else if (base.includes("time") && base.includes("without time zone")) {
    label = "time";
  }
  if (isArray) label = `${label}[]`;
  if (label.length <= 18) return label;
  return `${label.slice(0, 17)}…`;
}

function isDateType(type: string): boolean {
  return DATE_TYPES.has(type.toLowerCase());
}

function isIsoDateString(value: string): boolean {
  return ISO_DATE_RE.test(value);
}

function formatDbDate(value: string, type: string): string {
  const isDateOnly = type.toLowerCase() === "date";
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (isDateOnly && match) {
    return `${match[3]}/${match[2]}/${match[1]}`;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()} ${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

export function formatCellValue(value: unknown, type: string): FormattedCell {
  if (value === null || value === undefined) {
    return { text: "NULL", kind: "null", fullText: "NULL" };
  }
  if (typeof value === "boolean") {
    return {
      text: value ? "true" : "false",
      kind: "boolean",
      fullText: String(value),
    };
  }
  if (typeof value === "number") {
    return { text: String(value), kind: "number", fullText: String(value) };
  }
  if (typeof value === "object") {
    const fullText = JSON.stringify(value, null, 2);
    return { text: JSON.stringify(value), kind: "json", fullText };
  }
  const text = String(value);
  if (isDateType(type) && isIsoDateString(text)) {
    return { text: formatDbDate(text, type), kind: "date", fullText: text };
  }
  return { text, kind: "text", fullText: text };
}

export function cellToText(value: unknown): string {
  if (value === null || value === undefined) return "NULL";
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}

function escapeCsvCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  const text =
    typeof value === "object" ? JSON.stringify(value) : String(value);
  if (/[",\n\r]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

export function toCsv(
  columns: AdminDbResultColumn[],
  rows: unknown[][],
): string {
  const header = columns.map((column) => escapeCsvCell(column.name)).join(",");
  const body = rows
    .map((row) => row.map((cell) => escapeCsvCell(cell)).join(","))
    .join("\n");
  return `\uFEFF${header}\n${body}`;
}

export function toJson(
  columns: AdminDbResultColumn[],
  rows: unknown[][],
): string {
  return JSON.stringify({ columns, rows }, null, 2);
}

export function exportFilename(extension: "csv" | "json"): string {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, "0");
  return `admin-query-${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(
    now.getDate(),
  )}-${pad(now.getHours())}${pad(now.getMinutes())}.${extension}`;
}

export function downloadFile(
  filename: string,
  content: string,
  mimeType: string,
): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

export async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* fallback bên dưới */
  }
  try {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    const ok = document.execCommand("copy");
    textarea.remove();
    return ok;
  } catch {
    return false;
  }
}

export function truncateText(value: string, max = 200): string {
  if (value.length <= max) return value;
  return `${value.slice(0, max)}…`;
}

export function isQueryHistoryItem(value: unknown): value is QueryHistoryItem {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    typeof item.id === "string" &&
    typeof item.sql === "string" &&
    typeof item.ranAt === "string" &&
    typeof item.durationMs === "number" &&
    typeof item.rowCount === "number" &&
    typeof item.ok === "boolean" &&
    (item.error === undefined || typeof item.error === "string")
  );
}

export const EXAMPLE_QUERIES: ExampleQuery[] = [
  {
    id: "recent-users",
    title: "Người dùng mới nhất",
    description: "Danh sách tài khoản mới tạo, kèm họ tên và vai trò.",
    sql: `SELECT u.id, u.email, u.full_name, u.role, u.status, u.created_at
FROM users u
ORDER BY u.created_at DESC
LIMIT 20;`,
  },
  {
    id: "course-enrollment",
    title: "Khóa học & sĩ số",
    description: "Số sinh viên đang hoạt động trong từng khóa học.",
    sql: `SELECT c.id, c.title, COUNT(e.student_id) AS student_count
FROM courses c
LEFT JOIN enrollments e ON e.course_id = c.id AND e.status = 'active'
GROUP BY c.id, c.title
ORDER BY student_count DESC
LIMIT 20;`,
  },
  {
    id: "recent-sessions",
    title: "Phiên học gần đây",
    description: "Các phiên học mới nhất kèm email sinh viên và khóa học.",
    sql: `SELECT ls.id, u.email, c.id AS course_id, ls.status,
       ls.started_at, ls.ended_at
FROM learning_sessions ls
JOIN enrollments e ON e.id = ls.enrollment_id
JOIN users u ON u.id = e.student_id
JOIN courses c ON c.id = e.course_id
ORDER BY ls.started_at DESC
LIMIT 20;`,
  },
  {
    id: "gaze-daily",
    title: "Mẫu gaze theo ngày",
    description: "Số mẫu gaze ghi nhận trong 7 ngày gần nhất.",
    sql: `SELECT date_trunc('day', gs.event_time) AS day, COUNT(*) AS samples
FROM gaze_samples gs
WHERE gs.event_time >= now() - interval '7 days'
GROUP BY 1
ORDER BY 1 DESC;`,
  },
  {
    id: "recent-quiz",
    title: "Quiz gần đây",
    description: "Các lượt làm quiz mới nhất và điểm số.",
    sql: `SELECT qa.id, u.email, qa.status, qa.score, qa.max_score,
       qa.started_at, qa.submitted_at
FROM quiz_attempts qa
JOIN enrollments e ON e.id = qa.enrollment_id
JOIN users u ON u.id = e.student_id
ORDER BY qa.started_at DESC
LIMIT 20;`,
  },
];
