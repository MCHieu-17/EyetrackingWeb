const COLORS = [
  "#257de0",
  "#f47230",
  "#00b894",
  "#f2a600",
  "#ee7fac",
  "#008a17",
  "#6a4ce2",
  "#ec4647",
  "#0e7490",
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
