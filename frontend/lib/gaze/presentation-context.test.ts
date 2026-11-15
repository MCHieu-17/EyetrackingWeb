import { describe, expect, it } from "vitest";

import {
  createPresentationRequestTracker,
  presentationContextKey,
} from "./presentation-context";

const BASE = {
  sessionId: "session-1",
  lessonId: "lesson-1",
  surface: "lesson" as const,
  slideId: "slide-1",
  slideIndex: 0,
};

describe("presentationContextKey", () => {
  it("changes when session, lesson, surface or slide changes", () => {
    const key = presentationContextKey(BASE);

    expect(
      presentationContextKey({ ...BASE, sessionId: "session-2" }),
    ).not.toBe(key);
    expect(presentationContextKey({ ...BASE, lessonId: "lesson-2" })).not.toBe(
      key,
    );
    expect(presentationContextKey({ ...BASE, slideId: "slide-2" })).not.toBe(
      key,
    );
    expect(presentationContextKey({ ...BASE, slideIndex: 1 })).not.toBe(key);
    expect(
      presentationContextKey({ ...BASE, surface: "quiz", slideId: null }),
    ).not.toBe(key);
  });

  it("treats quiz content as independent from the slide index", () => {
    const quiz = {
      ...BASE,
      surface: "quiz" as const,
      slideId: null,
    };

    expect(presentationContextKey({ ...quiz, slideIndex: 0 })).toBe(
      presentationContextKey({ ...quiz, slideIndex: 9 }),
    );
  });
});

describe("createPresentationRequestTracker", () => {
  it("only accepts the latest request when responses resolve out of order", () => {
    const tracker = createPresentationRequestTracker();
    const first = tracker.begin("presentation-a");
    const second = tracker.begin("presentation-b");

    // Response của request mới về trước.
    expect(tracker.isActive(second)).toBe(true);
    expect(tracker.isActive(first)).toBe(false);

    // Response cũ về sau không được overwrite context mới.
    expect(tracker.isActive(first)).toBe(false);
    expect(tracker.isActive(second)).toBe(true);
  });

  it("invalidates all pending requests when the context becomes inactive", () => {
    const tracker = createPresentationRequestTracker();
    const token = tracker.begin("presentation-a");

    tracker.invalidate();

    expect(tracker.isActive(token)).toBe(false);
  });

  it("invalidates a pending request even when the key is reused", () => {
    const tracker = createPresentationRequestTracker();
    const first = tracker.begin("same-key");
    const second = tracker.begin("same-key");

    expect(tracker.isActive(first)).toBe(false);
    expect(tracker.isActive(second)).toBe(true);
  });
});
