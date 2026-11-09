import type { EnrollStatus, StudentRow } from "@/lib/types/domain";

export type SortColumn = "name" | "status" | "lastActive";
type SortDir = "asc" | "desc";
export type SortState = { column: SortColumn; dir: SortDir };

const STATUS_ORDER: Record<EnrollStatus, number> = {
  active: 0,
  completed: 1,
  dropped: 2,
};

/** Quy đổi chuỗi "5 phút trước"… thành số phút để sắp xếp. */
export function relativeMinutes(value: string): number {
  const text = value.toLowerCase();
  if (text.includes("vừa")) return 0;
  const amount = Number(text.match(/\d+/)?.[0] ?? 999999);
  if (text.includes("phút")) return amount;
  if (text.includes("giờ")) return amount * 60;
  if (text.includes("ngày")) return amount * 60 * 24;
  if (text.includes("tuần")) return amount * 60 * 24 * 7;
  return 999999;
}

/** Lọc theo tên hoặc mã sinh viên (không phân biệt hoa thường). */
export function filterStudents(students: StudentRow[], query: string): StudentRow[] {
  const q = query.trim().toLowerCase();
  return students.filter(
    (student) =>
      !q ||
      student.name.toLowerCase().includes(q) ||
      student.code.toLowerCase().includes(q),
  );
}

/** Sắp xếp bản sao danh sách học viên theo cột/chiều đang chọn. */
export function sortStudents(students: StudentRow[], sort: SortState): StudentRow[] {
  const factor = sort.dir === "asc" ? 1 : -1;
  return [...students].sort((a, b) => {
    if (sort.column === "name") return factor * a.name.localeCompare(b.name, "vi");
    if (sort.column === "status") {
      return factor * (STATUS_ORDER[a.status] - STATUS_ORDER[b.status]);
    }
    return factor * (relativeMinutes(a.lastActive) - relativeMinutes(b.lastActive));
  });
}

/** Lọc rồi sắp xếp — đầu vào duy nhất cho bảng học viên. */
export function sortAndFilterStudents(
  students: StudentRow[],
  query: string,
  sort: SortState,
): StudentRow[] {
  return sortStudents(filterStudents(students, query), sort);
}

/** Đếm học viên theo trạng thái để hiển thị phần tóm tắt. */
export function countStudentsByStatus(
  students: StudentRow[],
): Record<EnrollStatus, number> {
  return students.reduce<Record<EnrollStatus, number>>(
    (counts, student) => {
      counts[student.status] += 1;
      return counts;
    },
    { active: 0, completed: 0, dropped: 0 },
  );
}
