import { describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { AoiDefinitionInput } from "@/lib/api/aoi";
import { AoiRow } from "./aoi-row";

const definition: AoiDefinitionInput = {
  code: "slide_1_text_1",
  name: "TEXT",
  label: "AOI_1",
  parentId: "slide_1",
  geometry: { xMin: 0.1, yMin: 0.1, xMax: 0.4, yMax: 0.4 },
  isContainer: false,
  kind: "text",
  isActive: true,
};

function renderRow(overrides: Partial<Parameters<typeof AoiRow>[0]> = {}) {
  const onDelete = vi.fn();
  render(
    <AoiRow
      definition={definition}
      selected={false}
      hovered={false}
      canManage
      subtitle="Nhãn: AOI_1"
      icon="ri-text"
      onSelect={vi.fn()}
      onHover={vi.fn()}
      onRename={vi.fn()}
      onDelete={onDelete}
      {...overrides}
    />,
  );
  return { onDelete };
}

describe("AoiRow", () => {
  it("không còn nút ẩn; nút xóa xác nhận rồi gọi onDelete", () => {
    const { onDelete } = renderRow();
    expect(screen.queryByLabelText("Ẩn vùng")).toBeNull();
    expect(screen.getByText("Nhãn: AOI_1")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Xóa vùng"));
    expect(screen.getByText("Xóa vùng này?")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Xóa"));
    expect(onDelete).toHaveBeenCalledTimes(1);
    cleanup();
  });

  it("vùng chưa đánh dấu vẫn có bật lại và xóa", () => {
    renderRow({ inactive: true, onRestore: vi.fn() });
    expect(screen.getByLabelText("Bật lại vùng")).toBeInTheDocument();
    expect(screen.getByLabelText("Xóa vùng")).toBeInTheDocument();
    cleanup();
  });
});
