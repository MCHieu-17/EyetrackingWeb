import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ReplayView } from "@/lib/types/visualization";
import { ReplayTimeline } from "./replay-timeline";

function makeView(overrides: Partial<ReplayView> = {}): ReplayView {
  return {
    contentViewId: "view-1",
    sequenceNo: 0,
    surface: "lesson",
    sessionId: "session-1",
    lessonId: "lesson-1",
    lessonTitle: "Bài 1",
    lessonKind: "lesson",
    slideId: "slide-1",
    slideTitle: "Slide 1",
    pageNumber: 1,
    pdfUrl: "/media/assets/a/file",
    startedAt: "2026-01-01T00:00:00Z",
    endedAt: null,
    firstSampleAt: null,
    lastSampleAt: null,
    sampleCount: 0,
    okSampleCount: 0,
    gazeCount: 0,
    onSlideGazeCount: 0,
    trackedDurationMs: 0,
    dwellMs: 15000,
    counted: true,
    analysisStatus: "ready",
    analysisVersion: "gaze-metrics-v6",
    viewport: { width: 1280, height: 800 },
    slideAois: [],
    layouts: [],
    aoiStats: [],
    ...overrides,
  };
}

afterEach(cleanup);

describe("ReplayTimeline", () => {
  it("hiển thị lượt không có sample cùng các badge ngắn/thiếu layout", () => {
    render(
      <ReplayTimeline
        views={[
          makeView({
            contentViewId: "empty-view",
            slideTitle: "Slide không mẫu",
            sampleCount: 0,
            dwellMs: 0,
            counted: false,
          }),
        ]}
        currentIndex={0}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByText("Slide không mẫu")).toBeInTheDocument();
    expect(screen.getByText("Không có mẫu")).toBeInTheDocument();
    expect(screen.getByText("Ngắn <1s")).toBeInTheDocument();
    expect(screen.getByText("Thiếu layout")).toBeInTheDocument();
  });

  it("dùng dwellMs cho nhãn thời lượng thay vì span sample", () => {
    render(
      <ReplayTimeline
        views={[makeView({ dwellMs: 15000 })]}
        currentIndex={0}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByText("0:15")).toBeInTheDocument();
  });

  it("đánh dấu các lần xuất hiện lặp của cùng slide", () => {
    render(
      <ReplayTimeline
        views={[
          makeView({ contentViewId: "view-1", slideTitle: "Slide 2" }),
          makeView({ contentViewId: "view-2", slideTitle: "Slide 3" }),
          makeView({ contentViewId: "view-3", slideTitle: "Slide 2" }),
          makeView({ contentViewId: "view-4", slideTitle: "Slide 2" }),
        ]}
        currentIndex={0}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getAllByText("Slide 2")).toHaveLength(3);
    expect(screen.queryByText("Lần 1")).toBeNull();
    expect(screen.getByText("Lần 2")).toBeInTheDocument();
    expect(screen.getByText("Lần 3")).toBeInTheDocument();
  });

  it("giữ nhóm bài riêng khi cùng bài xuất hiện không liên tiếp", () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ReplayTimeline
        views={[
          makeView({
            contentViewId: "a-1",
            lessonId: "lesson-a",
            lessonTitle: "Bài A",
            slideId: "slide-a",
          }),
          makeView({
            contentViewId: "b-1",
            lessonId: "lesson-b",
            lessonTitle: "Bài B",
            slideId: "slide-b",
          }),
          makeView({
            contentViewId: "a-2",
            lessonId: "lesson-a",
            lessonTitle: "Bài A",
            slideId: "slide-a",
          }),
        ]}
        currentIndex={0}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getAllByText("Bài A")).toHaveLength(2);
    expect(screen.getByText("Lần 2")).toBeInTheDocument();
    expect(errorSpy).not.toHaveBeenCalled();
  });

  it("hiển thị tổng số lượt, số lượt ngắn và chọn đúng index", () => {
    const onSelect = vi.fn();
    const views = [
      makeView({
        contentViewId: "short-1",
        slideTitle: "Lượt ngắn",
        counted: false,
      }),
      makeView({
        contentViewId: "counted-1",
        slideTitle: "Lượt đủ",
        counted: true,
      }),
      makeView({
        contentViewId: "short-2",
        slideTitle: "Lượt ngắn 2",
        counted: false,
      }),
    ];

    render(
      <ReplayTimeline
        views={views}
        allViews={views}
        shortViewCount={2}
        currentIndex={0}
        onSelect={onSelect}
      />,
    );

    expect(screen.getByText(/3 lượt xem trong ca/)).toBeInTheDocument();
    expect(screen.getByText("2 lượt ngắn")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Lượt đủ"));
    expect(onSelect).toHaveBeenCalledWith(1);
  });

  it("cho biết số lượt bị ẩn khi bật bộ lọc", () => {
    render(
      <ReplayTimeline
        views={[makeView({ contentViewId: "counted-1", slideTitle: "Lượt đủ" })]}
        allViews={[
          makeView({ contentViewId: "short-1", counted: false }),
          makeView({ contentViewId: "counted-1" }),
        ]}
        shortViewCount={1}
        filtered
        currentIndex={0}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByText(/1\/2 lượt xem/)).toBeInTheDocument();
    expect(screen.getByText("đã ẩn 1 lượt ngắn")).toBeInTheDocument();
  });
});
