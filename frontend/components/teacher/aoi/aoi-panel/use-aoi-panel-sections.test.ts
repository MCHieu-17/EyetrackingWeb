import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { AoiDefinitionInput } from "@/lib/api/aoi";
import { buildAoiPanelModel } from "@/components/teacher/aoi/aoi-panel/panel-model";
import { useAoiPanelSections } from "@/components/teacher/aoi/aoi-panel/use-aoi-panel-sections";

function definition(
  code: string,
  overrides: Partial<AoiDefinitionInput> = {},
): AoiDefinitionInput {
  return { code, name: code, geometry: {}, ...overrides };
}

const model = buildAoiPanelModel(
  [
    definition("slide_1", { isContainer: true, kind: "system" }),
    definition("text_1", { kind: "text" }),
    definition("image_1", { kind: "image" }),
    definition("custom_1", { kind: "custom", isActive: false }),
  ],
  [],
);

describe("useAoiPanelSections", () => {
  it("bật/tắt trạng thái thu gọn của từng nhóm", () => {
    const { result } = renderHook(() =>
      useAoiPanelSections({ tab: "slide", selectedCode: null, model }),
    );

    act(() => result.current.toggleSection("text"));
    expect(result.current.collapsed.text).toBe(true);

    act(() => result.current.toggleSection("text"));
    expect(result.current.collapsed.text).toBe(false);
  });

  it("tự mở nhóm chứa vùng đang chọn", () => {
    const { result, rerender } = renderHook(
      ({ selectedCode }: { selectedCode: string | null }) =>
        useAoiPanelSections({ tab: "slide", selectedCode, model }),
      { initialProps: { selectedCode: null as string | null } },
    );

    act(() => result.current.toggleSection("image"));
    expect(result.current.collapsed.image).toBe(true);

    rerender({ selectedCode: "image_1" });
    expect(result.current.collapsed.image).toBe(false);
  });

  it("tự mở nhóm Chưa đánh dấu khi chọn vùng đã bỏ đánh dấu", () => {
    const { result, rerender } = renderHook(
      ({ selectedCode }: { selectedCode: string | null }) =>
        useAoiPanelSections({ tab: "slide", selectedCode, model }),
      { initialProps: { selectedCode: null as string | null } },
    );

    act(() => result.current.toggleSection("inactive"));
    expect(result.current.collapsed.inactive).toBe(true);

    rerender({ selectedCode: "custom_1" });
    expect(result.current.collapsed.inactive).toBe(false);
    expect(result.current.selection).toEqual({
      selectedInactive: true,
      selectedKind: null,
    });
  });
});
