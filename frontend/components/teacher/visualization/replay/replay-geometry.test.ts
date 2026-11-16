import { describe, expect, it } from "vitest";
import type {
  ReplayLayout,
  ReplaySample,
  ReplayView,
} from "@/lib/types/visualization";
import {
  findSampleAt,
  firstSampleForLabel,
  formatDwellThreshold,
  formatDuration,
  layoutForSample,
  playbackDurationMs,
  rectToStage,
  sampleStagePoint,
  slideRectToStage,
  stageAspect,
  viewDwellMs,
} from "./replay-geometry";

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
    firstSampleAt: "2026-01-01T00:00:00Z",
    lastSampleAt: "2026-01-01T00:00:10Z",
    sampleCount: 10,
    okSampleCount: 10,
    gazeCount: 10,
    onSlideGazeCount: 5,
    trackedDurationMs: 10000,
    dwellMs: 12000,
    counted: true,
    analysisStatus: "ready",
    analysisVersion: "gaze-metrics-v6",
    viewport: {
      width: 1280,
      height: 800,
    },
    slideAois: [],
    layouts: [],
    aoiStats: [],
    ...overrides,
  };
}

function makeLayout(overrides: Partial<ReplayLayout> = {}): ReplayLayout {
  return {
    id: "layout-1",
    layoutNo: 0,
    slideRect: { left: 0.2, top: 0.2, width: 0.6, height: 0.6 },
    capturedAt: "2026-01-01T00:00:00Z",
    uiRegions: [],
    ...overrides,
  };
}

function makeSample(overrides: Partial<ReplaySample> = {}): ReplaySample {
  return {
    id: 1,
    offsetMs: 0,
    eventTime: "2026-01-01T00:00:00Z",
    sequence: 0,
    layoutId: "layout-1",
    status: "ok",
    viewportX: 0.5,
    viewportY: 0.5,
    slideX: 0.5,
    slideY: 0.5,
    aoiLabel: "SLIDE_AOI_1",
    qualityFlags: {},
    ...overrides,
  };
}

describe("replay geometry", () => {
  it("dùng trực tiếp slide rect của layout hiện tại", () => {
    const rect = slideRectToStage(makeLayout());
    expect(rect).not.toBeNull();
    expect(rect!.left).toBeCloseTo(0.2);
    expect(rect!.top).toBeCloseTo(0.2);
    expect(rect!.width).toBeCloseTo(0.6);
    expect(rect!.height).toBeCloseTo(0.6);
  });

  it("quy đổi rect AOI UI sang stage", () => {
    expect(
      rectToStage({ xMin: 0.1, yMin: 0.2, xMax: 0.6, yMax: 0.5 }),
    ).toEqual({ left: 0.1, top: 0.2, width: 0.5, height: 0.3 });
    expect(rectToStage({ xMin: 0.5, yMin: 0, xMax: 0.5, yMax: 1 })).toBeNull();
  });

  it("dùng toạ độ viewport hiện tại của sample", () => {
    expect(sampleStagePoint(makeSample())).toEqual({ x: 0.5, y: 0.5 });
    expect(
      sampleStagePoint(
        makeSample({ viewportX: null, viewportY: null }),
      ),
    ).toBeNull();
  });

  it("chọn layout theo sample rồi fallback layout cuối", () => {
    const first = makeLayout({ id: "layout-1" });
    const second = makeLayout({ id: "layout-2" });
    const view = makeView({ layouts: [first, second] });
    expect(layoutForSample(view, makeSample({ layoutId: "layout-2" }))?.id).toBe(
      "layout-2",
    );
    expect(layoutForSample(view, makeSample({ layoutId: null }))?.id).toBe(
      "layout-2",
    );
  });

  it("tìm sample theo thời gian và nhãn", () => {
    const samples = [
      makeSample({ id: 1, offsetMs: 0, aoiLabel: "A" }),
      makeSample({ id: 2, offsetMs: 500, aoiLabel: "B" }),
      makeSample({ id: 3, offsetMs: 900, aoiLabel: "B" }),
    ];
    expect(findSampleAt(samples, 0)?.id).toBe(1);
    expect(findSampleAt(samples, 600)?.id).toBe(2);
    expect(findSampleAt(samples, 5000)?.id).toBe(3);
    expect(firstSampleForLabel(samples, "B")?.id).toBe(2);
  });

  it("tách dwell thực tế khỏi span sample dùng để phát lại", () => {
    const view = makeView();
    expect(viewDwellMs(view)).toBe(12000);
    expect(playbackDurationMs(view)).toBe(10000);

    expect(viewDwellMs(makeView({ dwellMs: -500 }))).toBe(0);
    expect(
      playbackDurationMs(
        makeView({ firstSampleAt: null, lastSampleAt: null }),
      ),
    ).toBe(0);
  });

  it("tính aspect ratio và format thời gian", () => {
    const view = makeView();
    expect(formatDuration(65000)).toBe("1:05");
    expect(formatDuration(3665000)).toBe("1:01:05");
    expect(formatDwellThreshold(1000)).toBe("1s");
    expect(formatDwellThreshold(1500)).toBe("1.5s");
    expect(stageAspect(view)).toBeCloseTo(1.6);
  });
});
