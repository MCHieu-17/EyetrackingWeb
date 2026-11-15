import { describe, expect, it } from "vitest";
import {
  findCitationSlideIndex,
  findNextLesson,
  getNextSlideIndex,
  getPreviousSlideIndex,
  getReaderLayoutKey,
  hashPayload,
  isGazeDotVisible,
  resolveActiveLessonId,
} from "./reader-helpers";

describe("hashPayload", () => {
  it("is deterministic for the same payload", () => {
    expect(hashPayload({ a: 1, b: [2, 3] })).toBe(hashPayload({ a: 1, b: [2, 3] }));
  });

  it("changes when the payload changes", () => {
    expect(hashPayload({ a: 1 })).not.toBe(hashPayload({ a: 2 }));
  });

  it("returns a 64-character hex digest", () => {
    expect(hashPayload([1, 2, 3])).toMatch(/^[0-9a-f]{64}$/);
  });
});

describe("resolveActiveLessonId", () => {
  const lessons = [{ id: "a" }, { id: "b" }, { id: "c" }];

  it("keeps the active lesson when the outline is empty", () => {
    expect(
      resolveActiveLessonId({
        requestedLessonId: "b",
        activeLessonId: "x",
        lessons: [],
      }),
    ).toBe("x");
  });

  it("prefers a valid requested lesson", () => {
    expect(
      resolveActiveLessonId({
        requestedLessonId: "b",
        activeLessonId: "a",
        lessons,
      }),
    ).toBe("b");
  });

  it("falls back to the active lesson", () => {
    expect(
      resolveActiveLessonId({
        requestedLessonId: "z",
        activeLessonId: "c",
        lessons,
      }),
    ).toBe("c");
  });

  it("falls back to the first lesson", () => {
    expect(
      resolveActiveLessonId({
        requestedLessonId: null,
        activeLessonId: "z",
        lessons,
      }),
    ).toBe("a");
  });
});

describe("getReaderLayoutKey", () => {
  it("returns reader layout keys", () => {
    expect(getReaderLayoutKey(false, false)).toBe("reader");
    expect(getReaderLayoutKey(false, true)).toBe("reader-chat");
  });

  it("returns quiz layout keys", () => {
    expect(getReaderLayoutKey(true, false)).toBe("quiz");
    expect(getReaderLayoutKey(true, true)).toBe("quiz-chat");
  });
});

describe("findNextLesson", () => {
  const lessons = [{ id: "a" }, { id: "b" }, { id: "c" }];

  it("returns the next lesson", () => {
    expect(findNextLesson(lessons, "a")).toEqual({ id: "b" });
  });

  it("returns undefined at the end", () => {
    expect(findNextLesson(lessons, "c")).toBeUndefined();
  });

  it("returns the first lesson when the active lesson is unknown", () => {
    expect(findNextLesson(lessons, "z")).toEqual({ id: "a" });
  });
});

describe("isGazeDotVisible", () => {
  it("requires a matching lesson and slide", () => {
    expect(isGazeDotVisible({ x: 0.1, y: 0.2, key: "a:0" }, "a", 0)).toBe(true);
    expect(isGazeDotVisible({ x: 0.1, y: 0.2, key: "a:0" }, "a", 1)).toBe(false);
    expect(isGazeDotVisible(null, "a", 0)).toBe(false);
  });
});

describe("getNextSlideIndex", () => {
  it("advances within the slide range", () => {
    expect(getNextSlideIndex(0, 3)).toBe(1);
    expect(getNextSlideIndex(1, 3)).toBe(2);
  });

  it("stops at the last slide", () => {
    expect(getNextSlideIndex(2, 3)).toBe(2);
    expect(getNextSlideIndex(9, 3)).toBe(2);
  });

  it("returns 0 when there are no slides", () => {
    expect(getNextSlideIndex(0, 0)).toBe(0);
    expect(getNextSlideIndex(4, 0)).toBe(0);
  });
});

describe("getPreviousSlideIndex", () => {
  it("moves back one slide", () => {
    expect(getPreviousSlideIndex(2)).toBe(1);
  });

  it("stops at the first slide", () => {
    expect(getPreviousSlideIndex(0)).toBe(0);
    expect(getPreviousSlideIndex(-3)).toBe(0);
  });
});

describe("findCitationSlideIndex", () => {
  const slides = [
    { id: "v1" },
    { id: "v2" },
    { id: "v3" },
  ];

  it("prefers the slide id", () => {
    expect(findCitationSlideIndex({ slideId: "v2" }, slides)).toBe(1);
  });

  it("falls back to the slide index", () => {
    expect(
      findCitationSlideIndex({ slideId: "missing", slideIndex: 2 }, slides),
    ).toBe(2);
  });

  it("returns -1 when neither matches", () => {
    expect(
      findCitationSlideIndex({ slideId: "missing", slideIndex: 9 }, slides),
    ).toBe(-1);
    expect(findCitationSlideIndex({}, slides)).toBe(-1);
  });
});
