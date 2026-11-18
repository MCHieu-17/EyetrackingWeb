import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { AoiSaveStatus } from "../use-aoi-autosave";
import { PanelActions } from "./panel-actions";

type Controller = Parameters<typeof PanelActions>[0]["controller"];

afterEach(cleanup);

function renderActions({
  status,
  error = null,
}: {
  status: AoiSaveStatus;
  error?: string | null;
}) {
  const retry = vi.fn();
  const controller: Controller = {
    tab: "slide",
    canManage: true,
    mode: "edit",
    activeSave: {
      status,
      error,
      dirty: status === "error",
      pending: false,
      flush: vi.fn(),
      retry,
    },
  };
  render(
    <PanelActions controller={controller} hint={null} onShowHint={vi.fn()} />,
  );
  return { retry };
}

describe("PanelActions", () => {
  it("hiển thị lỗi lưu thật thay vì chỉ báo chung chung", () => {
    renderActions({ status: "error", error: "Origin không hợp lệ" });

    expect(screen.getByText("Không lưu được")).toBeInTheDocument();
    expect(screen.getByText("Origin không hợp lệ")).toBeInTheDocument();
  });

  it("bấm Thử lại gọi retry của autosave", () => {
    const { retry } = renderActions({
      status: "error",
      error: "Origin không hợp lệ",
    });

    fireEvent.click(screen.getByText("Thử lại"));
    expect(retry).toHaveBeenCalledTimes(1);
  });

  it("không hiện lỗi khi đã lưu", () => {
    renderActions({ status: "saved" });

    expect(screen.getByText("Đã lưu")).toBeInTheDocument();
    expect(screen.queryByText("Thử lại")).toBeNull();
  });
});
