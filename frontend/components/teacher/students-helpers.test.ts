import { describe, expect, it } from "vitest";

import {
  countStudentsByStatus,
  filterStudents,
  relativeMinutes,
  sortAndFilterStudents,
  sortStudents,
  type SortState,
} from "@/components/teacher/students-helpers";
import type { StudentRow } from "@/lib/types/domain";

function makeStudent(overrides: Partial<StudentRow> = {}): StudentRow {
  return {
    id: "student-1",
    name: "Nguyễn Văn A",
    code: "SV001",
    color: "#000",
    attention: null,
    lastActive: "5 phút trước",
    status: "active",
    lessons: [],
    ...overrides,
  };
}

describe("relativeMinutes", () => {
  it("nhận diện vừa xong", () => {
    expect(relativeMinutes("Vừa xong")).toBe(0);
  });

  it("quy đổi phút, giờ, ngày, tuần", () => {
    expect(relativeMinutes("5 phút trước")).toBe(5);
    expect(relativeMinutes("2 giờ trước")).toBe(120);
    expect(relativeMinutes("3 ngày trước")).toBe(3 * 60 * 24);
    expect(relativeMinutes("1 tuần trước")).toBe(7 * 60 * 24);
  });

  it("trả về giá trị lớn cho chuỗi không nhận diện được", () => {
    expect(relativeMinutes("không rõ")).toBe(999999);
  });
});

describe("filterStudents", () => {
  const students = [
    makeStudent({ id: "1", name: "Nguyễn Văn A", code: "SV001" }),
    makeStudent({ id: "2", name: "Trần Thị B", code: "SV002" }),
  ];

  it("trả về toàn bộ khi query rỗng", () => {
    expect(filterStudents(students, "  ")).toEqual(students);
  });

  it("lọc theo tên không phân biệt hoa thường", () => {
    expect(filterStudents(students, "nguyễn").map((s) => s.id)).toEqual(["1"]);
  });

  it("lọc theo mã sinh viên", () => {
    expect(filterStudents(students, "sv002").map((s) => s.id)).toEqual(["2"]);
  });

  it("trả về rỗng khi không khớp", () => {
    expect(filterStudents(students, "xyz")).toEqual([]);
  });
});

describe("sortStudents", () => {
  const students = [
    makeStudent({ id: "1", name: "B", status: "completed", lastActive: "2 giờ trước" }),
    makeStudent({ id: "2", name: "A", status: "active", lastActive: "10 phút trước" }),
    makeStudent({ id: "3", name: "C", status: "dropped", lastActive: "1 ngày trước" }),
  ];

  it("sắp xếp theo tên tăng/giảm", () => {
    const asc: SortState = { column: "name", dir: "asc" };
    const desc: SortState = { column: "name", dir: "desc" };

    expect(sortStudents(students, asc).map((s) => s.id)).toEqual(["2", "1", "3"]);
    expect(sortStudents(students, desc).map((s) => s.id)).toEqual(["3", "1", "2"]);
  });

  it("sắp xếp theo thứ tự trạng thái active → completed → dropped", () => {
    const sort: SortState = { column: "status", dir: "asc" };
    expect(sortStudents(students, sort).map((s) => s.id)).toEqual(["2", "1", "3"]);
  });

  it("sắp xếp theo hoạt động gần nhất", () => {
    const sort: SortState = { column: "lastActive", dir: "asc" };
    expect(sortStudents(students, sort).map((s) => s.id)).toEqual(["2", "1", "3"]);
  });

  it("không sửa mảng gốc", () => {
    const original = [...students];
    sortStudents(students, { column: "name", dir: "asc" });
    expect(students).toEqual(original);
  });
});

describe("sortAndFilterStudents", () => {
  it("lọc trước rồi sắp xếp", () => {
    const students = [
      makeStudent({ id: "1", name: "B", code: "SV001" }),
      makeStudent({ id: "2", name: "A", code: "SV002" }),
      makeStudent({ id: "3", name: "C", code: "SV003" }),
    ];

    expect(
      sortAndFilterStudents(students, "SV00", { column: "name", dir: "asc" }).map(
        (s) => s.id,
      ),
    ).toEqual(["2", "1", "3"]);
  });
});

describe("countStudentsByStatus", () => {
  it("đếm theo từng trạng thái", () => {
    const students = [
      makeStudent({ status: "active" }),
      makeStudent({ status: "active" }),
      makeStudent({ status: "completed" }),
      makeStudent({ status: "dropped" }),
    ];

    expect(countStudentsByStatus(students)).toEqual({
      active: 2,
      completed: 1,
      dropped: 1,
    });
  });

  it("trả về 0 cho danh sách rỗng", () => {
    expect(countStudentsByStatus([])).toEqual({
      active: 0,
      completed: 0,
      dropped: 0,
    });
  });
});
