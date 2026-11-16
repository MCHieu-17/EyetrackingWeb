import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CourseVisitRow } from "@/lib/api/visits";
import { SummaryFilters } from "./summary-filters";

const visit: CourseVisitRow = {
  id: "visit-1",
  enrollmentId: "enrollment-1",
  studentId: "student-1",
  studentName: "Nguyễn Văn A",
  studentCode: "12345678",
  courseId: "course-1",
  startedAt: "2026-01-01T00:00:00Z",
  endedAt: null,
  lastSeenAt: "2026-01-01T00:10:00Z",
  status: "ended",
  lessonSessionCount: 1,
  gazeCount: 100,
  onSlideGazeCount: 80,
  trackedDurationMs: 60000,
};

function renderFilters(overrides: {
  onlyCounted?: boolean;
  onOnlyCounted?: (value: boolean) => void;
} = {}) {
  const onOnlyCounted = overrides.onOnlyCounted ?? vi.fn();
  render(
    <SummaryFilters
      visits={[visit]}
      lessons={[{ id: "lesson-1", title: "Bài 1" }]}
      scope="cohort"
      onScope={vi.fn()}
      studentId="student-1"
      onStudent={vi.fn()}
      selectedStudentIds={[]}
      onSelectedStudents={vi.fn()}
      visitId=""
      onVisit={vi.fn()}
      lessonId=""
      onLesson={vi.fn()}
      from=""
      onFrom={vi.fn()}
      to=""
      onTo={vi.fn()}
      surface="all"
      onSurface={vi.fn()}
      includeDropped={false}
      onIncludeDropped={vi.fn()}
      onlyCounted={overrides.onlyCounted ?? false}
      onOnlyCounted={onOnlyCounted}
      onReset={vi.fn()}
    />,
  );
  return { onOnlyCounted };
}

afterEach(cleanup);

describe("SummaryFilters", () => {
  it("mặc định tắt bộ lọc lượt ngắn", () => {
    renderFilters();
    const toggle = screen.getByRole("switch", {
      name: "Chỉ tính lượt >= ngưỡng",
      hidden: true,
    });
    expect(toggle).toHaveAttribute("aria-checked", "false");
  });

  it("bật bộ lọc gọi onOnlyCounted(true)", () => {
    const { onOnlyCounted } = renderFilters();
    fireEvent.click(
      screen.getByRole("switch", {
        name: "Chỉ tính lượt >= ngưỡng",
        hidden: true,
      }),
    );
    expect(onOnlyCounted).toHaveBeenCalledWith(true);
  });
});
