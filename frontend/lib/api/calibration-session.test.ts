import { beforeEach, describe, expect, it } from "vitest";

import { ensureGazeAffinityCookie } from "./calibration-session";

function affinityValue(): string | null {
  const row = document.cookie
    .split("; ")
    .find((item) => item.startsWith("gaze_affinity="));
  return row ? row.slice("gaze_affinity=".length) : null;
}

describe("ensureGazeAffinityCookie", () => {
  beforeEach(() => {
    document.cookie = "gaze_affinity=; Max-Age=0; Path=/";
  });

  it("tạo cookie affinity trước request gaze đầu tiên", () => {
    expect(affinityValue()).toBeNull();
    ensureGazeAffinityCookie();
    expect(affinityValue()).toBeTruthy();
  });

  it("không ghi đè cookie đã có", () => {
    ensureGazeAffinityCookie();
    const first = affinityValue();
    ensureGazeAffinityCookie();
    expect(affinityValue()).toBe(first);
  });
});
