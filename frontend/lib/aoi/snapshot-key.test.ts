import { describe, expect, it } from "vitest";

import { aoiSnapshotCacheKey } from "./snapshot-key";

const BASE = {
  sessionId: "session-1",
  presentationId: "presentation-1",
  viewportWidth: 1280,
  viewportHeight: 720,
  layoutKey: "reader",
  rectsKey: "slide:0.1,0.2,0.3,0.4",
};

describe("aoiSnapshotCacheKey", () => {
  it("is stable for the same context and geometry", () => {
    expect(aoiSnapshotCacheKey(BASE)).toBe(aoiSnapshotCacheKey({ ...BASE }));
  });

  it("includes session and presentation ids", () => {
    const key = aoiSnapshotCacheKey(BASE);

    expect(
      aoiSnapshotCacheKey({ ...BASE, sessionId: "session-2" }),
    ).not.toBe(key);
    // Hai presentation cùng hình học vẫn phải tạo layout riêng.
    expect(
      aoiSnapshotCacheKey({ ...BASE, presentationId: "presentation-2" }),
    ).not.toBe(key);
  });

  it("changes with viewport, layout key or measured rects", () => {
    const key = aoiSnapshotCacheKey(BASE);

    expect(aoiSnapshotCacheKey({ ...BASE, viewportWidth: 1920 })).not.toBe(key);
    expect(aoiSnapshotCacheKey({ ...BASE, layoutKey: "reader-chat" })).not.toBe(
      key,
    );
    expect(
      aoiSnapshotCacheKey({ ...BASE, rectsKey: "slide:0,0,1,1" }),
    ).not.toBe(key);
  });
});
