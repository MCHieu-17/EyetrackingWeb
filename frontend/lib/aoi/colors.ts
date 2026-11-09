const COLORS = [
  "#e11d48",
  "#ea580c",
  "#ca8a04",
  "#16a34a",
  "#0891b2",
  "#2563eb",
  "#7c3aed",
  "#db2777",
  "#0f766e",
];

/**
 * Màu ổn định cho một code vùng. Cùng code luôn ra cùng màu để overlay và
 * danh sách bên cạnh khớp nhau.
 */
export function colorFor(code: string): string {
  let hash = 0;
  for (let index = 0; index < code.length; index += 1) {
    hash = (hash * 31 + code.charCodeAt(index)) >>> 0;
  }
  return COLORS[hash % COLORS.length];
}
