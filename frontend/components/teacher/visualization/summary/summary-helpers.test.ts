import { describe, expect, it } from "vitest";
import type {
  AoiSummary,
  AoiSummaryAoi,
  AoiSummaryLesson,
  AoiSummaryQuery,
} from "@/lib/types/visualization";
import {
  buildHeatmapQuery,
  compositionForAois,
  compositionForLesson,
  csvForSummary,
  percent,
  shareLabel,
  topAois,
  visibleAois,
} from "./summary-helpers";

function aoi(overrides: Partial<AoiSummaryAoi> = {}): AoiSummaryAoi {
  return {
    label: "SLIDE_AOI_1",
    name: "AOI 1",
    domain: "slide",
    durationMs: 1000,
    sampleCount: 10,
    share: 0.1,
    studentCount: 1,
    slideCount: 1,
    mixedSlides: false,
    isUnlabeled: false,
    ...overrides,
  };
}

function lesson(overrides: Partial<AoiSummaryLesson> = {}): AoiSummaryLesson {
  return {
    lessonId: "lesson-1",
    lessonTitle: "Bài 1",
    lessonKind: "lesson",
    durationMs: 3000,
    sampleCount: 30,
    aois: [
      aoi({ label: "A", name: "Vùng A", durationMs: 2000 }),
      aoi({ label: "B", name: "Vùng B", durationMs: 1000 }),
    ],
    ...overrides,
  };
}

describe("summary helpers", () => {
  it("lọc AOI rỗng và gộp phần vượt topN vào Khác", () => {
    const rows = [
      aoi({ label: "A", durationMs: 500 }),
      aoi({ label: "B", durationMs: 400 }),
      aoi({ label: "C", durationMs: 300 }),
      aoi({ label: "D", durationMs: 200 }),
      aoi({ label: "E", durationMs: 0, sampleCount: 0 }),
    ];
    expect(visibleAois(rows)).toHaveLength(4);
    const top = topAois(rows, 2);
    expect(top.map((item) => item.label)).toEqual(["A", "B", "other"]);
    expect(top[2].durationMs).toBe(500);
  });

  it("tính phần trăm và nhãn share", () => {
    expect(percent(25, 100)).toBe(25);
    expect(percent(0, 0)).toBe(0);
    expect(shareLabel(0.456)).toBe("46%");
  });

  it("dựng composition theo bài, gộp Khác", () => {
    const top = [
      aoi({ label: "A", name: "Vùng A", durationMs: 2000 }),
      aoi({ label: "C", name: "Vùng C", durationMs: 0 }),
    ];
    const segments = compositionForLesson(lesson(), top);
    expect(segments.map((segment) => segment.label)).toEqual(["A", "other"]);
    expect(segments[0].percent).toBeCloseTo(66.666, 2);
    expect(segments[1].durationMs).toBe(1000);
  });

  it("dựng composition cho học viên", () => {
    const segments = compositionForAois(
      [aoi({ label: "A", durationMs: 500 }), aoi({ label: "B", durationMs: 500 })],
      1000,
      [aoi({ label: "A", name: "Vùng A" })],
    );
    expect(segments.map((segment) => segment.label)).toEqual(["A", "other"]);
    expect(segments[0].percent).toBe(50);
    expect(segments[1].percent).toBe(50);
  });

  it("xuất CSV có header và escape dấu nháy", () => {
    const summary = {
      byAoi: [aoi({ name: 'Vùng "đặc biệt"' })],
    } as AoiSummary;
    const csv = csvForSummary(summary);
    expect(csv.split("\n")[0]).toContain("Nhan AOI");
    expect(csv).toContain('"Vùng ""đặc biệt"""');
  });

  it("buildHeatmapQuery bỏ filter bài/surface, giữ filter học viên/ca/ngày", () => {
    const base: AoiSummaryQuery = {
      studentIds: ["student-1"],
      visitIds: ["visit-1"],
      lessonIds: ["lesson-1", "lesson-2"],
      from: "2026-01-01",
      to: "2026-01-31",
      surface: "quiz",
      includeShort: true,
    };

    const query = buildHeatmapQuery(base, "slide-9");

    expect(query).toEqual({
      studentIds: ["student-1"],
      visitIds: ["visit-1"],
      from: "2026-01-01",
      to: "2026-01-31",
      includeShort: true,
      lessonIds: [],
      surface: "lesson",
      slideId: "slide-9",
    });
    expect(base.lessonIds).toEqual(["lesson-1", "lesson-2"]);
  });
});
