import { describe, expect, it } from "vitest";

import type { AoiDefinition, AoiSet } from "@/lib/api/aoi";
import {
  countCustom,
  nextCustomCode,
  nextUiCustomCode,
  pickLatest,
  toInputs,
} from "@/lib/aoi/editor-helpers";

function makeDefinition(
  overrides: Partial<AoiDefinition> = {},
): AoiDefinition {
  return {
    id: "id-1",
    code: "slide_1",
    name: "Slide 1",
    parentId: null,
    geometry: { xMin: 0, yMin: 0, xMax: 1, yMax: 1 },
    isContainer: true,
    kind: "system",
    isActive: true,
    ...overrides,
  };
}

function makeSet(overrides: Partial<AoiSet> = {}): AoiSet {
  return {
    id: "set-1",
    scope: "slide",
    slideVersionId: "sv-1",
    uiSchemaVersion: null,
    revision: 1,
    state: "draft",
    createdBy: "user-1",
    createdAt: "2026-01-01T00:00:00Z",
    publishedAt: null,
    definitions: [],
    ...overrides,
  };
}

describe("pickLatest", () => {
  it("trả về null khi không có dữ liệu", () => {
    expect(pickLatest(undefined)).toBeNull();
    expect(pickLatest([])).toBeNull();
  });

  it("ưu tiên bộ draft", () => {
    const draft = makeSet({ id: "draft", state: "draft" });
    const published = makeSet({ id: "published", state: "published" });

    expect(pickLatest([published, draft])).toBe(draft);
  });

  it("dùng bộ published khi không có draft", () => {
    const published = makeSet({ id: "published", state: "published" });
    const archived = makeSet({ id: "archived", state: "archived" });

    expect(pickLatest([archived, published])).toBe(published);
  });

  it("bỏ qua bộ archived", () => {
    expect(pickLatest([makeSet({ state: "archived" })])).toBeNull();
  });
});

describe("toInputs", () => {
  it("chuyển parentId từ id sang code", () => {
    const root = makeDefinition({ id: "root-id", code: "slide_1" });
    const child = makeDefinition({
      id: "child-id",
      code: "slide_1_custom_1",
      parentId: "root-id",
      isContainer: false,
      kind: "custom",
    });

    expect(toInputs([root, child])).toEqual([
      {
        code: "slide_1",
        name: "Slide 1",
        parentId: null,
        geometry: { xMin: 0, yMin: 0, xMax: 1, yMax: 1 },
        isContainer: true,
        kind: "system",
        isActive: true,
      },
      {
        code: "slide_1_custom_1",
        name: "Slide 1",
        parentId: "slide_1",
        geometry: { xMin: 0, yMin: 0, xMax: 1, yMax: 1 },
        isContainer: false,
        kind: "custom",
        isActive: true,
      },
    ]);
  });

  it("bỏ vùng no_label", () => {
    const noLabel = makeDefinition({ id: "no-label-id", code: "no_label" });
    const normal = makeDefinition({ id: "normal-id", code: "slide_1" });

    expect(toInputs([noLabel, normal]).map((item) => item.code)).toEqual([
      "slide_1",
    ]);
  });

  it("giữ parentId gốc khi không tìm thấy parent", () => {
    const orphan = makeDefinition({
      id: "orphan-id",
      code: "orphan",
      parentId: "missing-id",
    });

    expect(toInputs([orphan])[0].parentId).toBe("missing-id");
  });
});

describe("nextCustomCode", () => {
  it("bắt đầu từ 1 khi chưa có vùng", () => {
    expect(nextCustomCode([], "slide_1")).toBe("slide_1_custom_1");
  });

  it("bỏ qua các code đã tồn tại", () => {
    const definitions = [
      { code: "slide_1_custom_1" },
      { code: "slide_1_custom_2" },
    ] as Parameters<typeof nextCustomCode>[0];

    expect(nextCustomCode(definitions, "slide_1")).toBe("slide_1_custom_3");
  });

  it("lấp khoảng trống đầu tiên", () => {
    const definitions = [
      { code: "slide_1_custom_1" },
      { code: "slide_1_custom_3" },
    ] as Parameters<typeof nextCustomCode>[0];

    expect(nextCustomCode(definitions, "slide_1")).toBe("slide_1_custom_2");
  });
});

describe("nextUiCustomCode", () => {
  it("bắt đầu từ 1 khi chưa có vùng", () => {
    expect(nextUiCustomCode([])).toBe("ui_custom_1");
  });

  it("bỏ qua các code đã tồn tại", () => {
    const definitions = [
      { code: "ui_custom_1" },
      { code: "ui_custom_2" },
    ] as Parameters<typeof nextUiCustomCode>[0];

    expect(nextUiCustomCode(definitions)).toBe("ui_custom_3");
  });
});

describe("countCustom", () => {
  it("chỉ đếm vùng kind custom", () => {
    const definitions = [
      { kind: "custom" },
      { kind: "ui" },
      { kind: "custom" },
      { kind: "system" },
    ] as Parameters<typeof countCustom>[0];

    expect(countCustom(definitions)).toBe(2);
  });

  it("trả về 0 cho mảng rỗng", () => {
    expect(countCustom([])).toBe(0);
  });
});
