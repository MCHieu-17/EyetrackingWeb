import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AoiHeatmap } from "@/lib/types/visualization";
import { HeatmapCard } from "./heatmap-card";

const mocks = vi.hoisted(() => ({
  useLessonSlidesAdmin: vi.fn(),
  useAoiHeatmap: vi.fn(),
}));

vi.mock("@/hooks/use-teacher", () => ({
  useLessonSlidesAdmin: mocks.useLessonSlidesAdmin,
}));

vi.mock("@/hooks/use-visualization", () => ({
  useAoiHeatmap: mocks.useAoiHeatmap,
}));

vi.mock("@/components/pdf/lazy-pdf-page", () => ({
  LazyPdfPage: () => <div data-testid="pdf-page" />,
}));

const lessons = [{ id: "lesson-1", title: "Bài 1" }];

function emptyGrid(): number[][] {
  return Array.from({ length: 24 }, () => Array<number>(24).fill(0));
}

function makeHeatmap(overrides: Partial<AoiHeatmap> = {}): AoiHeatmap {
  return {
    slide: {
      id: "slide-1",
      title: "Slide 1",
      pageNumber: 1,
      pdfUrl: "/media/assets/a/file",
      lessonTitle: "Bài 1",
    },
    grid: emptyGrid(),
    max: 0,
    onSlideSampleCount: 0,
    ...overrides,
  };
}

function renderCard(heatmap: AoiHeatmap) {
  mocks.useLessonSlidesAdmin.mockReturnValue({
    data: [
      {
        id: "slide-1",
        orderIndex: 0,
        title: "Slide 1",
        pdfUrl: "/media/assets/a/file",
        pageNumber: 1,
        pageCount: 1,
      },
    ],
    isLoading: false,
    isError: false,
  });
  mocks.useAoiHeatmap.mockReturnValue({
    data: heatmap,
    isLoading: false,
    isError: false,
  });

  return render(
    <HeatmapCard
      courseId="course-1"
      baseQuery={{ lessonIds: ["lesson-2"], surface: "quiz" }}
      lessons={lessons}
    />,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(cleanup);

describe("HeatmapCard", () => {
  it("gửi query heatmap độc lập filter bài/surface và đặt lưới trên canvas PDF", () => {
    const grid = emptyGrid();
    grid[2][21] = 5;
    renderCard(makeHeatmap({ grid, max: 5, onSlideSampleCount: 5 }));

    expect(mocks.useAoiHeatmap).toHaveBeenCalledWith(
      "course-1",
      expect.objectContaining({
        slideId: "slide-1",
        lessonIds: [],
        surface: "lesson",
      }),
      true,
    );
    expect(screen.getByLabelText("Lưới heatmap 24x24")).toHaveClass("z-20");
  });

  it("báo cần phân tích lại khi có view stale và chưa có grid", () => {
    renderCard(
      makeHeatmap({ max: 0, staleViewCount: 2, analyzedViewCount: 0 }),
    );

    expect(
      screen.getByText("Dữ liệu gaze cần phân tích lại"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/2 lượt xem chưa được phân tích lại/),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Chưa có điểm nhìn trên slide này"),
    ).not.toBeInTheDocument();
  });

  it("giữ thông báo chưa có dữ liệu khi không có view stale", () => {
    renderCard(
      makeHeatmap({ max: 0, staleViewCount: 0, analyzedViewCount: 0 }),
    );

    expect(
      screen.getByText("Chưa có điểm nhìn trên slide này"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Dữ liệu gaze cần phân tích lại"),
    ).not.toBeInTheDocument();
  });

  it("không báo cần phân tích lại khi đã có view phân tích nhưng slide không có mẫu", () => {
    renderCard(
      makeHeatmap({ max: 0, staleViewCount: 2, analyzedViewCount: 1 }),
    );

    expect(
      screen.getByText("Chưa có điểm nhìn trên slide này"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Dữ liệu gaze cần phân tích lại"),
    ).not.toBeInTheDocument();
  });

  it("cảnh báo thiếu dữ liệu khi heatmap có điểm nhưng còn view stale", () => {
    const grid = emptyGrid();
    grid[10][10] = 3;
    renderCard(
      makeHeatmap({
        grid,
        max: 3,
        onSlideSampleCount: 3,
        analyzedViewCount: 1,
        staleViewCount: 2,
      }),
    );

    expect(
      screen.getByText(/2 lượt xem chưa được phân tích lại; heatmap có thể thiếu/),
    ).toBeInTheDocument();
    expect(screen.getByText("1 lượt xem đã phân tích")).toBeInTheDocument();
  });
});
