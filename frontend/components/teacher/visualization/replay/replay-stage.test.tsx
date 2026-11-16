import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ReplayView } from "@/lib/types/visualization";
import { ReplayStage } from "./replay-stage";

vi.mock("@/components/pdf/lazy-pdf-page", () => ({
  LazyPdfPage: () => <div data-testid="pdf-page" />,
}));

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
    dwellMs: 2000,
    counted: true,
    analysisStatus: "pending",
    analysisVersion: "",
    viewport: { width: 1280, height: 800 },
    slideAois: [],
    layouts: [],
    aoiStats: [],
    ...overrides,
  };
}

function renderStage(view: ReplayView) {
  return render(
    <ReplayStage
      view={view}
      samples={[]}
      currentSample={null}
      showAllAois
      showLabels
      showTrail={false}
      pinnedLabel={null}
    />,
  );
}

afterEach(cleanup);

describe("ReplayStage", () => {
  it("dựng PDF toàn khung và cảnh báo khi thiếu layout", () => {
    renderStage(makeView({ layouts: [], pdfUrl: "/media/assets/a/file" }));

    expect(screen.getByTestId("pdf-page")).toBeInTheDocument();
    expect(screen.getByText("Thiếu layout")).toBeInTheDocument();
    expect(screen.queryByText("Thiếu layout của lượt xem")).toBeNull();
  });

  it("không crash khi không có sample, layout lẫn PDF", () => {
    renderStage(makeView({ layouts: [], pdfUrl: null }));

    expect(screen.getByText("Thiếu layout của lượt xem")).toBeInTheDocument();
    expect(
      screen.getByText("Chưa có mẫu gaze cho lượt xem này"),
    ).toBeInTheDocument();
  });
});
