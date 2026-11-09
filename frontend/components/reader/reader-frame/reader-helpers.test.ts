import { describe, expect, it } from "vitest";
import type { ModuleItem } from "@/lib/types/domain";
import {
  allLessons,
  getGazeStatus,
  getNextLesson,
  isAtLastSlide,
} from "./reader-helpers";

const modules: ModuleItem[] = [
  {
    id: "m1",
    orderIndex: 1,
    title: "M1",
    lessons: [
      { id: "l1", title: "L1", kind: "lesson", slideCount: 1 },
      { id: "l2", title: "L2", kind: "quiz", slideCount: 0 },
    ],
  },
  {
    id: "m2",
    orderIndex: 2,
    title: "M2",
    lessons: [{ id: "l3", title: "L3", kind: "lesson", slideCount: 2 }],
  },
];

describe("allLessons", () => {
  it("flattens lessons across modules", () => {
    expect(allLessons(modules).map((lesson) => lesson.id)).toEqual(["l1", "l2", "l3"]);
  });

  it("returns an empty list for no modules", () => {
    expect(allLessons([])).toEqual([]);
  });
});

describe("getNextLesson", () => {
  const lessons = allLessons(modules);

  it("returns the next lesson across module boundaries", () => {
    expect(getNextLesson(lessons, "l2")?.id).toBe("l3");
  });

  it("returns undefined at the end", () => {
    expect(getNextLesson(lessons, "l3")).toBeUndefined();
  });

  it("returns the first lesson when the active lesson is unknown", () => {
    expect(getNextLesson(lessons, "missing")?.id).toBe("l1");
  });
});

describe("isAtLastSlide", () => {
  it("is true only for the last non-empty slide", () => {
    expect(isAtLastSlide(2, 3)).toBe(true);
    expect(isAtLastSlide(1, 3)).toBe(false);
    expect(isAtLastSlide(0, 0)).toBe(false);
  });
});

describe("getGazeStatus", () => {
  it("maps the gaze source and calibration flag", () => {
    expect(getGazeStatus("real", true)).toBe("active");
    expect(getGazeStatus("off", true)).toBe("disconnected");
    expect(getGazeStatus("off", false)).toBe("off");
    expect(getGazeStatus(null, false)).toBe("off");
    expect(getGazeStatus(null, true)).toBe("disconnected");
  });
});
