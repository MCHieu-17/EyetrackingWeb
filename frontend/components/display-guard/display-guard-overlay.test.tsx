import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { DisplayGuardOverlay } from "./display-guard-overlay";

afterEach(cleanup);

describe("DisplayGuardOverlay", () => {
  it("renders nothing when not blocked", () => {
    const { container } = render(
      <DisplayGuardOverlay
        blocked={false}
        reason={null}
        zoomPercent={100}
        onRecheck={() => {}}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("explains page zoom with the current percentage", () => {
    render(
      <DisplayGuardOverlay
        blocked
        reason="page_zoom"
        zoomPercent={125}
        onRecheck={() => {}}
      />,
    );

    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    expect(screen.getByText("Trình duyệt đang phóng to")).toBeInTheDocument();
    expect(screen.getByText("125%")).toBeInTheDocument();
    expect(screen.getByText(/Ctrl\+0/)).toBeInTheDocument();
  });

  it("explains pinch zoom", () => {
    render(
      <DisplayGuardOverlay
        blocked
        reason="pinch_zoom"
        zoomPercent={100}
        onRecheck={() => {}}
      />,
    );

    expect(
      screen.getByText("Bạn đang thu phóng bằng cử chỉ"),
    ).toBeInTheDocument();
  });

  it("explains the Fullscreen API", () => {
    render(
      <DisplayGuardOverlay
        blocked
        reason="fullscreen"
        zoomPercent={100}
        onRecheck={() => {}}
      />,
    );

    expect(screen.getByText("Đang bật toàn màn hình")).toBeInTheDocument();
    expect(screen.getByText(/Esc hoặc F11/)).toBeInTheDocument();
  });

  it("explains browser fullscreen", () => {
    render(
      <DisplayGuardOverlay
        blocked
        reason="browser_fullscreen"
        zoomPercent={100}
        onRecheck={() => {}}
      />,
    );

    expect(
      screen.getByText("Cửa sổ đang toàn màn hình"),
    ).toBeInTheDocument();
  });

  it("calls recheck without offering a dismiss action", () => {
    const onRecheck = vi.fn();
    render(
      <DisplayGuardOverlay
        blocked
        reason={null}
        zoomPercent={100}
        onRecheck={onRecheck}
      />,
    );

    expect(screen.getByText("Hiển thị chưa ổn định")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /đóng|hủy|bỏ qua/i }),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Kiểm tra lại" }));
    expect(onRecheck).toHaveBeenCalledTimes(1);
  });
});
