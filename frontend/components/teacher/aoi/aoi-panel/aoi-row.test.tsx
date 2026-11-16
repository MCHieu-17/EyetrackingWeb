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
  const onLabelChange = vi.fn<(label: string) => string | null>(() => null);
  render(
    <AoiRow
      definition={definition}
      selected={false}
      hovered={false}
      canManage
      icon="ri-text"
      labelValue="AOI_1"
      labelPrefix="SLIDE_"
      onLabelChange={onLabelChange}
      onSelect={vi.fn()}
      onHover={vi.fn()}
      onRename={vi.fn()}
      onDelete={onDelete}
      {...overrides}
    />,
  );
  return { onDelete, onLabelChange };
}

function labelInput(): HTMLInputElement {
  return screen.getByLabelText("Nhãn phân tích") as HTMLInputElement;
}

describe("AoiRow", () => {
  it("không còn nút ẩn; nút xóa xác nhận rồi gọi onDelete", () => {
    const { onDelete } = renderRow();
    expect(screen.queryByLabelText("Ẩn vùng")).toBeNull();

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

  it("hiện ô nhãn phân tích với tiền tố SLIDE_", () => {
    renderRow();
    const input = labelInput();
    expect(input).toHaveValue("AOI_1");
    expect(input).toHaveAttribute("placeholder", "AOI_THANHCHAT");
    expect(screen.getByText("Nhãn phân tích")).toBeInTheDocument();
    expect(screen.getByText("SLIDE_")).toBeInTheDocument();
    cleanup();
  });

  it("commit nhãn khi blur", () => {
    const { onLabelChange } = renderRow();
    const input = labelInput();
    fireEvent.change(input, { target: { value: "AOI_THANHCHAT" } });
    fireEvent.blur(input);
    expect(onLabelChange).toHaveBeenCalledTimes(1);
    expect(onLabelChange).toHaveBeenCalledWith("AOI_THANHCHAT");
    cleanup();
  });

  it("commit nhãn khi nhấn Enter", () => {
    const { onLabelChange } = renderRow();
    const input = labelInput();
    fireEvent.change(input, { target: { value: "AOI_BANGBIEU" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onLabelChange).toHaveBeenCalledTimes(1);
    expect(onLabelChange).toHaveBeenCalledWith("AOI_BANGBIEU");
    cleanup();
  });

  it("hiện lỗi do controller trả về và giữ nhãn đang sửa", () => {
    const { onLabelChange } = renderRow();
    onLabelChange.mockReturnValue("Nhãn AOI_2 đã được dùng.");
    const input = labelInput();
    fireEvent.change(input, { target: { value: "AOI_2" } });
    fireEvent.blur(input);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Nhãn AOI_2 đã được dùng.",
    );
    expect(input).toHaveValue("AOI_2");
    cleanup();
  });

  it("Escape khôi phục nhãn hiện tại và không commit", () => {
    const { onLabelChange } = renderRow();
    const input = labelInput();
    fireEvent.change(input, { target: { value: "AOI_RAC" } });
    fireEvent.keyDown(input, { key: "Escape" });
    expect(input).toHaveValue("AOI_1");
    expect(onLabelChange).not.toHaveBeenCalled();
    expect(screen.queryByRole("alert")).toBeNull();
    cleanup();
  });
});
