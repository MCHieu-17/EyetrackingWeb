import { describe, expect, it } from "vitest";

import {
  isFrameForActiveContext,
  isValidGazeSequence,
  parseGazeFrameResponse,
} from "./frame-protocol";

const CONTEXT = {
  presentationId: "presentation-a",
  layoutGeneration: 2,
  surface: "lesson" as const,
};

describe("parseGazeFrameResponse", () => {
  it("parses a valid v2 frame and keeps server correlation fields", () => {
    const frame = parseGazeFrameResponse(
      JSON.stringify({
        ok: true,
        status: "ok",
        x: 0.25,
        y: 0.75,
        frameId: "frame-1",
        sequence: 7,
        captureMonotonicNs: 123456,
        presentationId: "presentation-a",
        layoutGeneration: 2,
      }),
      "2026-01-01T00:00:00.000Z",
    );

    expect(frame).toEqual({
      frameId: "frame-1",
      sequence: 7,
      captureMonotonicNs: 123456,
      eventTime: "2026-01-01T00:00:00.000Z",
      x: 0.25,
      y: 0.75,
      currentX: 0.25,
      currentY: 0.75,
      status: "ok",
      presentationId: "presentation-a",
      layoutGeneration: 2,
      surface: null,
    });
  });

  it("prefers the capture eventTime echoed by the gaze service", () => {
    const frame = parseGazeFrameResponse(
      JSON.stringify({
        ok: true,
        status: "ok",
        x: 0.2,
        y: 0.3,
        eventTime: "2026-01-01T00:00:00.123Z",
      }),
      "2026-01-01T00:00:01.000Z",
    );

    expect(frame?.eventTime).toBe("2026-01-01T00:00:00.123Z");
  });

  it("maps no_face without coordinates", () => {
    const frame = parseGazeFrameResponse({
      ok: false,
      status: "no_face",
      sequence: 3,
      presentationId: "presentation-a",
      layoutGeneration: 0,
    });

    expect(frame).toMatchObject({
      status: "no_face",
      x: null,
      y: null,
      sequence: 3,
    });
  });

  it("maps errors and malformed payloads to safe values", () => {
    expect(
      parseGazeFrameResponse({ ok: false, error: "no_face" })?.status,
    ).toBe("no_face");
    expect(
      parseGazeFrameResponse({ ok: false, error: "internal" })?.status,
    ).toBe("error");
    expect(parseGazeFrameResponse("not-json")).toBeNull();
    expect(parseGazeFrameResponse("null")).toBeNull();
    expect(parseGazeFrameResponse({ ok: true, x: "0.5", y: 0.5 })?.status).toBe(
      "error",
    );
  });

  it("normalises invalid sequence and layout generation to null", () => {
    const frame = parseGazeFrameResponse({
      ok: true,
      x: 0.1,
      y: 0.2,
      sequence: -1,
      layoutGeneration: 1.5,
      presentationId: "",
    });

    expect(frame?.sequence).toBeNull();
    expect(frame?.layoutGeneration).toBeNull();
    expect(frame?.presentationId).toBeNull();
  });
});

describe("isValidGazeSequence", () => {
  it("accepts only non-negative integers", () => {
    expect(isValidGazeSequence(0)).toBe(true);
    expect(isValidGazeSequence(12)).toBe(true);
    expect(isValidGazeSequence(null)).toBe(false);
    expect(isValidGazeSequence(-1)).toBe(false);
    expect(isValidGazeSequence(1.5)).toBe(false);
  });
});

describe("isFrameForActiveContext", () => {
  const frame = {
    sequence: 1,
    presentationId: "presentation-a",
    layoutGeneration: 2,
    surface: null,
  };

  it("accepts a frame for the active presentation and layout", () => {
    expect(isFrameForActiveContext(frame, CONTEXT)).toBe(true);
  });

  it("rejects stale presentation or layout generations", () => {
    expect(
      isFrameForActiveContext(
        { ...frame, presentationId: "presentation-old" },
        CONTEXT,
      ),
    ).toBe(false);
    expect(
      isFrameForActiveContext({ ...frame, layoutGeneration: 1 }, CONTEXT),
    ).toBe(false);
    expect(
      isFrameForActiveContext({ ...frame, layoutGeneration: null }, CONTEXT),
    ).toBe(false);
  });

  it("rejects null/duplicate-invalid sequences and inactive presentation", () => {
    expect(isFrameForActiveContext({ ...frame, sequence: null }, CONTEXT)).toBe(
      false,
    );
    expect(
      isFrameForActiveContext(
        { ...frame, presentationId: null },
        CONTEXT,
      ),
    ).toBe(false);
    expect(
      isFrameForActiveContext(frame, { ...CONTEXT, presentationId: null }),
    ).toBe(false);
  });

  it("checks surface only when the service echoes it", () => {
    expect(
      isFrameForActiveContext({ ...frame, surface: "quiz" }, CONTEXT),
    ).toBe(false);
    expect(
      isFrameForActiveContext({ ...frame, surface: "lesson" }, CONTEXT),
    ).toBe(true);
  });
});
