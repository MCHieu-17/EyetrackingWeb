import { describe, expect, it } from "vitest";

import { colorFor } from "@/lib/aoi/colors";

describe("colorFor", () => {
  it("trả về cùng màu cho cùng code", () => {
    expect(colorFor("slide_1_custom_1")).toBe(colorFor("slide_1_custom_1"));
    expect(colorFor("header")).toBe(colorFor("header"));
  });

  it("trả về mã màu hex hợp lệ", () => {
    expect(colorFor("lesson-content")).toMatch(/^#[0-9a-f]{6}$/);
  });

  it("có thể trả về màu khác nhau cho các code khác nhau", () => {
    const codes = ["a", "b", "c", "d", "e", "f", "g", "h", "i"];
    const colors = new Set(codes.map((code) => colorFor(code)));

    expect(colors.size).toBeGreaterThan(1);
  });

  it("ổn định với code rỗng", () => {
    expect(colorFor("")).toBe(colorFor(""));
  });
});
