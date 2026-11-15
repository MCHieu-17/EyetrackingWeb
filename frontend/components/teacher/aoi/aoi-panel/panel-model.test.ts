import { describe, expect, it } from "vitest";
import type { AoiDefinitionInput } from "@/lib/api/aoi";
import {
  buildAoiPanelModel,
  expandSelectedSections,
  resolveAoiSelection,
} from "@/components/teacher/aoi/aoi-panel/panel-model";

function definition(
  code: string,
  overrides: Partial<AoiDefinitionInput> = {},
): AoiDefinitionInput {
  return {
    code,
    name: code,
    geometry: {},
    ...overrides,
  };
}

const slideRoot = definition("slide_1", {
  name: "Slide 1",
  isContainer: true,
  kind: "system",
});
const activeText = definition("text_1", {
  name: "Tiêu đề",
  kind: "text",
  parentId: "slide_1",
  isActive: true,
});
const activeImage = definition("image_1", {
  name: "Hình",
  kind: "image",
  parentId: "slide_1",
});
const inactiveCustom = definition("custom_1", {
  name: "Vùng cũ",
  kind: "custom",
  parentId: "slide_1",
  isActive: false,
});
const fallbackKind = definition("misc_1", {
  name: "Không loại",
  parentId: "slide_1",
});

const slideDefinitions = [
  slideRoot,
  activeText,
  activeImage,
  inactiveCustom,
  fallbackKind,
];

const uiComponent = definition("header", { name: "Thanh trên", kind: "ui" });
const uiCustom = definition("ui_custom_1", {
  name: "Vùng tự vẽ",
  kind: "custom",
  geometry: { anchor: "header", xMin: 0, yMin: 0, xMax: 1, yMax: 1 },
});
const uiDefinitions = [uiComponent, uiCustom];

describe("buildAoiPanelModel", () => {
  it("tách container slide, vùng lá và vùng đã bỏ đánh dấu", () => {
    const model = buildAoiPanelModel(slideDefinitions, uiDefinitions);

    expect(model.slideRoot?.code).toBe("slide_1");
    expect(model.slideLeaves.map((item) => item.code)).toEqual([
      "text_1",
      "image_1",
      "custom_1",
      "misc_1",
    ]);
    expect(model.activeLeaves.map((item) => item.code)).toEqual([
      "text_1",
      "image_1",
      "misc_1",
    ]);
    expect(model.inactiveLeaves.map((item) => item.code)).toEqual([
      "custom_1",
    ]);
  });

  it("nhóm vùng hoạt động theo kind và bỏ qua container", () => {
    const model = buildAoiPanelModel(slideDefinitions, uiDefinitions);

    expect(Object.keys(model.slideGroups)).toEqual([
      "text",
      "image",
      "custom",
    ]);
    expect(model.slideGroups.text.map((item) => item.code)).toEqual([
      "text_1",
    ]);
    expect(model.slideGroups.custom.map((item) => item.code)).toEqual([
      "misc_1",
    ]);
  });

  it("không nhận container không phải slide làm gốc", () => {
    const model = buildAoiPanelModel(
      [
        definition("group_1", { isContainer: true, kind: "custom" }),
        activeText,
      ],
      [],
    );

    expect(model.slideRoot).toBeNull();
    expect(model.slideLeaves.map((item) => item.code)).toEqual(["text_1"]);
  });

  it("tách vùng giao diện và tính các phần còn chưa chọn", () => {
    const model = buildAoiPanelModel(slideDefinitions, uiDefinitions);

    expect(model.uiComponents.map((item) => item.code)).toEqual(["header"]);
    expect(model.uiCustom.map((item) => item.code)).toEqual(["ui_custom_1"]);
    expect(model.availableComponents.map((item) => item.code)).not.toContain(
      "header",
    );
    expect(model.availableComponents.map((item) => item.code)).toContain(
      "outline",
    );
  });

  it("loại mọi mã đã có khỏi danh sách phần chưa chọn", () => {
    const model = buildAoiPanelModel(
      [],
      [definition("outline", { kind: "custom" })],
    );

    expect(model.uiComponents).toEqual([]);
    expect(model.uiCustom.map((item) => item.code)).toEqual(["outline"]);
    expect(model.availableComponents.map((item) => item.code)).not.toContain(
      "outline",
    );
  });

  it("không sửa mảng đầu vào", () => {
    const snapshot = JSON.stringify(slideDefinitions);

    buildAoiPanelModel(slideDefinitions, uiDefinitions);

    expect(JSON.stringify(slideDefinitions)).toBe(snapshot);
  });
});

describe("resolveAoiSelection", () => {
  const model = buildAoiPanelModel(slideDefinitions, uiDefinitions);

  it("trả về rỗng khi chưa chọn vùng", () => {
    expect(
      resolveAoiSelection({ tab: "slide", selectedCode: null, model }),
    ).toEqual({ selectedInactive: false, selectedKind: null });
  });

  it("nhận diện vùng slide đang hoạt động và loại của nó", () => {
    expect(
      resolveAoiSelection({ tab: "slide", selectedCode: "image_1", model }),
    ).toEqual({ selectedInactive: false, selectedKind: "image" });
  });

  it("nhận diện vùng slide đã bỏ đánh dấu", () => {
    expect(
      resolveAoiSelection({ tab: "slide", selectedCode: "custom_1", model }),
    ).toEqual({ selectedInactive: true, selectedKind: null });
  });

  it("tra loại vùng giao diện trong cả phần ui và tự chọn", () => {
    expect(
      resolveAoiSelection({ tab: "ui", selectedCode: "header", model }),
    ).toEqual({ selectedInactive: false, selectedKind: "ui" });
    expect(
      resolveAoiSelection({ tab: "ui", selectedCode: "ui_custom_1", model }),
    ).toEqual({ selectedInactive: false, selectedKind: "custom" });
  });

  it("bỏ qua mã không tồn tại", () => {
    expect(
      resolveAoiSelection({ tab: "ui", selectedCode: "missing", model }),
    ).toEqual({ selectedInactive: false, selectedKind: null });
  });
});

describe("expandSelectedSections", () => {
  it("giữ nguyên object khi không có nhóm nào đang đóng", () => {
    const collapsed = { inactive: false, text: false };

    expect(
      expandSelectedSections(collapsed, {
        selectedInactive: true,
        selectedKind: "text",
      }),
    ).toBe(collapsed);
  });

  it("mở nhóm chứa vùng chưa đánh dấu đang chọn", () => {
    expect(
      expandSelectedSections(
        { inactive: true, text: true },
        { selectedInactive: true, selectedKind: null },
      ),
    ).toEqual({ inactive: false, text: true });
  });

  it("mở nhóm theo loại vùng đang chọn", () => {
    expect(
      expandSelectedSections(
        { inactive: true, image: true },
        { selectedInactive: false, selectedKind: "image" },
      ),
    ).toEqual({ inactive: true, image: false });
  });

  it("không sửa object đầu vào", () => {
    const collapsed = { text: true };

    expandSelectedSections(collapsed, {
      selectedInactive: false,
      selectedKind: "text",
    });

    expect(collapsed).toEqual({ text: true });
  });
});
