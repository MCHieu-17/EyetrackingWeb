import { describe, expect, it } from "vitest";

import type {
  AoiDefinition,
  AoiDefinitionInput,
  AoiCollection,
} from "@/lib/api/aoi";
import {
  collectAoiCodes,
  countCustom,
  hasStoredAois,
  nextCustomCode,
  nextSlideLabel,
  nextUiCustomCode,
  normalizeSlideLabelInput,
  firstAoiCollection,
  toInputs,
  validateSlideLabel,
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

function makeCollection(
  overrides: Partial<AoiCollection> = {},
): AoiCollection {
  return {
    id: "collection-1",
    scope: "slide",
    slideId: "slide-1",
    uiSchema: null,
    definitions: [],
    ...overrides,
  };
}

describe("firstAoiCollection", () => {
  it("trả về null khi không có dữ liệu", () => {
    expect(firstAoiCollection(undefined)).toBeNull();
    expect(firstAoiCollection([])).toBeNull();
  });

  it("trả về collection hiện hành đầu tiên", () => {
    const first = makeCollection({ id: "first" });
    const second = makeCollection({ id: "second" });
    expect(firstAoiCollection([first, second])).toBe(first);
  });
});

describe("hasStoredAois", () => {
  it("coi collection rỗng/chỉ no_label là chưa có AOI", () => {
    expect(hasStoredAois(null)).toBe(false);
    expect(hasStoredAois(makeCollection())).toBe(false);
    expect(
      hasStoredAois(
        makeCollection({
          definitions: [makeDefinition({ code: "no_label" })],
        }),
      ),
    ).toBe(false);
  });

  it("coi root container là đã có dữ liệu", () => {
    expect(
      hasStoredAois(
        makeCollection({ definitions: [makeDefinition({ code: "slide_1" })] }),
      ),
    ).toBe(true);
  });
});

describe("nextSlideLabel", () => {
  it("bắt đầu từ AOI_1", () => {
    expect(nextSlideLabel([])).toBe("AOI_1");
  });

  it("tăng theo nhãn lớn nhất", () => {
    const definitions = [
      { label: "AOI_2" },
      { label: "AOI_7" },
      { label: null },
    ] as Parameters<typeof nextSlideLabel>[0];
    expect(nextSlideLabel(definitions)).toBe("AOI_8");
  });
});

describe("normalizeSlideLabelInput", () => {
  it("giữ nguyên nhãn đã hợp lệ", () => {
    expect(normalizeSlideLabelInput("AOI_THANHCHAT")).toBe("AOI_THANHCHAT");
    expect(normalizeSlideLabelInput("  AOI_2  ")).toBe("AOI_2");
  });

  it("bỏ dấu, viết hoa và thay ký tự lạ bằng _", () => {
    expect(normalizeSlideLabelInput("thanh chát")).toBe("AOI_THANH_CHAT");
    expect(normalizeSlideLabelInput("Bảng biểu")).toBe("AOI_BANG_BIEU");
    expect(normalizeSlideLabelInput("Đường đi")).toBe("AOI_DUONG_DI");
    expect(normalizeSlideLabelInput("THANH-CHAT")).toBe("AOI_THANH_CHAT");
  });

  it("thêm tiền tố AOI_ khi thiếu", () => {
    expect(normalizeSlideLabelInput("thanhchat")).toBe("AOI_THANHCHAT");
    expect(normalizeSlideLabelInput("BANGBIEU")).toBe("AOI_BANGBIEU");
  });

  it("bỏ tiền tố SLIDE_", () => {
    expect(normalizeSlideLabelInput("SLIDE_AOI_THANHCHAT")).toBe(
      "AOI_THANHCHAT",
    );
    expect(normalizeSlideLabelInput("slide_thanhchat")).toBe("AOI_THANHCHAT");
  });

  it("trả về chuỗi rỗng khi không còn nội dung", () => {
    expect(normalizeSlideLabelInput("")).toBe("");
    expect(normalizeSlideLabelInput("   ")).toBe("");
    expect(normalizeSlideLabelInput("___")).toBe("");
    expect(normalizeSlideLabelInput("!!!")).toBe("");
    expect(normalizeSlideLabelInput("AOI_")).toBe("");
  });

  it("giới hạn tổng độ dài 64 ký tự", () => {
    const label = normalizeSlideLabelInput("a".repeat(100));
    expect(label).toHaveLength(64);
    expect(label.startsWith("AOI_")).toBe(true);
  });
});

describe("validateSlideLabel", () => {
  const root: AoiDefinitionInput = {
    code: "slide_1",
    name: "Slide 1",
    parentId: null,
    geometry: {},
    isContainer: true,
    kind: "system",
    isActive: true,
  };
  const leaf = (code: string, label: string | null): AoiDefinitionInput => ({
    code,
    name: code,
    label,
    parentId: "slide_1",
    geometry: {},
    isContainer: false,
    kind: "custom",
    isActive: true,
  });
  const definitions = [
    root,
    leaf("slide_1_custom_1", "AOI_THANHCHAT"),
    leaf("slide_1_custom_2", "AOI_2"),
  ];

  it("chấp nhận nhãn đúng dạng và không trùng", () => {
    expect(
      validateSlideLabel("AOI_BANGBIEU", definitions, "slide_1_custom_1"),
    ).toBeNull();
  });

  it("báo lỗi khi nhãn trống", () => {
    expect(
      validateSlideLabel("   ", definitions, "slide_1_custom_1"),
    ).toContain("không được để trống");
  });

  it("báo lỗi khi sai dạng AOI_", () => {
    expect(
      validateSlideLabel("THANHCHAT", definitions, "slide_1_custom_1"),
    ).toContain("AOI_");
    expect(
      validateSlideLabel(`AOI_${"A".repeat(61)}`, definitions, "slide_1_custom_1"),
    ).not.toBeNull();
  });

  it("báo lỗi khi trùng nhãn của vùng khác", () => {
    expect(
      validateSlideLabel("AOI_2", definitions, "slide_1_custom_1"),
    ).toContain("đã được dùng");
  });

  it("bỏ qua chính vùng hiện tại và container", () => {
    expect(
      validateSlideLabel("AOI_THANHCHAT", definitions, "slide_1_custom_1"),
    ).toBeNull();
    const withLabeledRoot = [{ ...root, label: "AOI_ROOT" }, ...definitions];
    expect(
      validateSlideLabel("AOI_ROOT", withLabeledRoot, "slide_1_custom_1"),
    ).toBeNull();
  });
});

describe("collectAoiCodes", () => {
  it("gom vùng con đệ quy", () => {
    const definitions = [
      { code: "root", parentId: null },
      { code: "child", parentId: "root" },
      { code: "grandchild", parentId: "child" },
      { code: "other", parentId: null },
    ] as Parameters<typeof collectAoiCodes>[0];
    expect([...collectAoiCodes(definitions, "root")]).toEqual([
      "root",
      "child",
      "grandchild",
    ]);
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

  it("giữ nhãn phân tích của vùng slide", () => {
    const leaf = makeDefinition({
      id: "leaf-id",
      code: "slide_1_text_1",
      label: "AOI_1",
      parentId: "root-id",
      isContainer: false,
      kind: "text",
    });
    expect(toInputs([leaf])[0].label).toBe("AOI_1");
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
