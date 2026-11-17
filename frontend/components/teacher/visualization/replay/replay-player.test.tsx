import type { ReactNode } from "react";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReplayView, VisitReplay } from "@/lib/types/visualization";
import { ReplayPlayer } from "./replay-player";

const mocks = vi.hoisted(() => ({
  invalidateQueries: vi.fn(),
  rebuildAoiHits: vi.fn(),
  useReplaySamples: vi.fn(),
}));

vi.mock("@tanstack/react-query", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-query")>();
  return {
    ...actual,
    useQueryClient: () => ({ invalidateQueries: mocks.invalidateQueries }),
  };
});

vi.mock("@/hooks/use-visualization", () => ({
  useReplaySamples: mocks.useReplaySamples,
}));

vi.mock("@/lib/api/aoi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/aoi")>();
  return { ...actual, rebuildAoiHits: mocks.rebuildAoiHits };
});

vi.mock("@/components/pdf/lazy-pdf-page", () => ({
  LazyPdfPage: () => <div data-testid="pdf-page" />,
}));

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: ReactNode }) => (
    <a href={href}>{children}</a>
  ),
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
    dwellMs: 5000,
    counted: true,
    analysisStatus: "ready",
    analysisVersion: "gaze-metrics-v6",
    viewport: { width: 1280, height: 800 },
    slideAois: [],
    layouts: [
      {
        id: "layout-1",
        layoutNo: 0,
        slideRect: { left: 0.1, top: 0.1, width: 0.8, height: 0.8 },
        capturedAt: "2026-01-01T00:00:00Z",
        uiRegions: [],
      },
    ],
    aoiStats: [],
    ...overrides,
  };
}

function makeReplay(views: ReplayView[]): VisitReplay {
  return {
    visit: {
      visitId: "visit-1",
      enrollmentId: "enrollment-1",
      studentId: "student-1",
      courseId: "course-1",
      startedAt: "2026-01-01T00:00:00Z",
      endedAt: null,
      status: "ended",
      lessonSessionCount: 1,
      contentViewCount: views.length,
      gazeCount: 8,
      onSlideGazeCount: 8,
      trackedDurationMs: 13400,
      fixationCount: 0,
      minDwellMs: 1000,
      shortViewCount: 1,
    },
    student: {
      id: "student-1",
      name: "Nguyễn Văn A",
      code: "12345678",
      email: "12345678@st.neu.edu.vn",
      enrollmentStatus: "active",
    },
    course: { id: "course-1", title: "Khóa học" },
    views,
    uiAois: [],
  };
}

const views = [
  makeView({
    contentViewId: "empty-view",
    slideTitle: "Slide không mẫu",
    sampleCount: 0,
    dwellMs: 5000,
    counted: true,
  }),
  makeView({
    contentViewId: "short-view",
    sequenceNo: 1,
    slideId: "slide-2",
    slideTitle: "Slide ngắn",
    pageNumber: 2,
    sampleCount: 3,
    dwellMs: 400,
    counted: false,
  }),
  makeView({
    contentViewId: "counted-view",
    sequenceNo: 2,
    slideId: "slide-3",
    slideTitle: "Slide đủ",
    pageNumber: 3,
    sampleCount: 5,
    dwellMs: 8000,
    counted: true,
  }),
];

beforeEach(() => {
  mocks.rebuildAoiHits.mockResolvedValue({ ok: true, runs: 1, completed: 0, failed: 0 });
  mocks.useReplaySamples.mockReturnValue({
    data: undefined,
    isLoading: false,
    isError: false,
    hasNextPage: false,
    isFetchingNextPage: false,
    fetchNextPage: vi.fn(),
  });
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.clearAllMocks();
});

describe("ReplayPlayer", () => {
  it("hiển thị cả lượt 0 sample và lượt ngắn mặc định", () => {
    render(<ReplayPlayer courseId="course-1" replay={makeReplay(views)} />);

    expect(screen.getByText("Slide không mẫu")).toBeInTheDocument();
    expect(screen.getByText("Slide ngắn")).toBeInTheDocument();
    expect(screen.getByText("Slide đủ")).toBeInTheDocument();
    expect(screen.getByText("3 lượt xem")).toBeInTheDocument();
    expect(screen.getAllByText("1 lượt ngắn").length).toBeGreaterThan(0);
  });

  it("xóa cache replay samples sau khi phân tích lại", async () => {
    vi.useFakeTimers();
    const pendingView = makeView({
      contentViewId: "pending-view",
      analysisStatus: "pending",
      slideId: "slide-1",
      slideTitle: "Slide chờ phân tích",
    });
    render(
      <ReplayPlayer courseId="course-1" replay={makeReplay([pendingView])} />,
    );

    await act(async () => {
      fireEvent.click(
        screen.getByRole("button", { name: /Phân tích lại bài này/i }),
      );
      await vi.runAllTimersAsync();
    });

    expect(mocks.rebuildAoiHits).toHaveBeenCalledWith({
      courseId: "course-1",
      lessonId: "lesson-1",
    });
    expect(mocks.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["visualization", "visit-replay", "visit-1"],
    });
    expect(mocks.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["visualization", "replay-samples", "visit-1"],
    });
  });

  it("bộ lọc ngưỡng mặc định tắt và ẩn lượt ngắn khi bật", () => {
    render(<ReplayPlayer courseId="course-1" replay={makeReplay(views)} />);

    const toggle = screen.getByRole("switch", {
      name: "Chỉ lượt >= ngưỡng",
    });
    expect(toggle).toHaveAttribute("aria-checked", "false");

    fireEvent.click(toggle);
    expect(screen.queryByText("Slide ngắn")).toBeNull();
    expect(screen.getByText("Slide không mẫu")).toBeInTheDocument();
    expect(screen.getByText("Slide đủ")).toBeInTheDocument();
    expect(screen.getByText(/2\/3 lượt xem/)).toBeInTheDocument();
  });
});
