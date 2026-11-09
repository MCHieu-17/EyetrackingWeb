import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createElement, useState } from "react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { aoiRectsKey, measureAoiRects } from "@/lib/aoi/measure";

const VIEWPORT_WIDTH = 1000;
const VIEWPORT_HEIGHT = 800;

function makeRect(left: number, top: number, width: number, height: number): DOMRect {
  return {
    x: left,
    y: top,
    left,
    top,
    width,
    height,
    right: left + width,
    bottom: top + height,
    toJSON: () => ({}),
  } as DOMRect;
}

function addAoi(code: string | null, bounds: DOMRect, parent: ParentNode = document.body): HTMLElement {
  const el = document.createElement("div");
  if (code !== null) el.dataset.aoi = code;
  el.getBoundingClientRect = () => bounds;
  parent.appendChild(el);
  return el;
}

beforeEach(() => {
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    writable: true,
    value: VIEWPORT_WIDTH,
  });
  Object.defineProperty(window, "innerHeight", {
    configurable: true,
    writable: true,
    value: VIEWPORT_HEIGHT,
  });
});

afterEach(() => {
  document.body.innerHTML = "";
});

describe("measureAoiRects", () => {
  it("trả về mảng rỗng khi không có phần tử data-aoi", () => {
    expect(measureAoiRects()).toEqual([]);
  });

  it("đo và chuẩn hoá rect theo viewport", () => {
    addAoi("slide-title", makeRect(100, 80, 300, 160));

    expect(measureAoiRects()).toEqual([
      { code: "slide-title", xMin: 0.1, yMin: 0.1, xMax: 0.4, yMax: 0.3 },
    ]);
  });

  it("bỏ qua phần tử thiếu code hoặc code rỗng", () => {
    addAoi(null, makeRect(0, 0, 100, 100));
    addAoi("   ", makeRect(0, 0, 100, 100));
    addAoi("hop-le", makeRect(0, 0, 100, 100));

    expect(measureAoiRects().map((rect) => rect.code)).toEqual(["hop-le"]);
  });

  it("bỏ qua rect không có diện tích", () => {
    addAoi("rong-0", makeRect(10, 10, 0, 100));
    addAoi("cao-0", makeRect(10, 10, 100, 0));
    addAoi("am", makeRect(10, 10, -20, -20));

    expect(measureAoiRects()).toEqual([]);
  });

  it("kẹp rect tràn viewport về khoảng 0..1", () => {
    addAoi("tran", makeRect(-100, -50, 1300, 1000));

    expect(measureAoiRects()).toEqual([
      { code: "tran", xMin: 0, yMin: 0, xMax: 1, yMax: 1 },
    ]);
  });

  it("bỏ qua rect nằm hoàn toàn ngoài viewport", () => {
    addAoi("ben-phai", makeRect(1200, 100, 100, 100));
    addAoi("ben-trai", makeRect(-300, 100, 100, 100));

    expect(measureAoiRects()).toEqual([]);
  });

  it("giữ nhiều rect cho cùng một code", () => {
    addAoi("chat-user", makeRect(0, 0, 100, 100));
    addAoi("chat-user", makeRect(200, 200, 100, 100));

    const rects = measureAoiRects();
    expect(rects).toHaveLength(2);
    expect(rects.map((rect) => rect.code)).toEqual(["chat-user", "chat-user"]);
    expect(rects[1]).toEqual({
      code: "chat-user",
      xMin: 0.2,
      yMin: 0.25,
      xMax: 0.3,
      yMax: 0.375,
    });
  });

  it("chỉ đo trong root được truyền vào", () => {
    const container = document.createElement("section");
    document.body.appendChild(container);
    addAoi("trong", makeRect(0, 0, 100, 100), container);
    addAoi("ngoai", makeRect(0, 0, 100, 100));

    expect(measureAoiRects(container).map((rect) => rect.code)).toEqual(["trong"]);
  });

  it("đo lại được sau khi DOM cập nhật", async () => {
    function Demo() {
      const [visible, setVisible] = useState(false);
      return createElement(
        "div",
        null,
        createElement("button", { type: "button", onClick: () => setVisible(true) }, "hiện"),
        visible ? createElement("div", { "data-aoi": "sau-click" }, "nội dung") : null,
      );
    }

    render(createElement(Demo));
    expect(measureAoiRects()).toEqual([]);

    await userEvent.click(screen.getByRole("button", { name: "hiện" }));

    const el = document.querySelector<HTMLElement>('[data-aoi="sau-click"]');
    expect(el).not.toBeNull();
    el!.getBoundingClientRect = () => makeRect(100, 80, 300, 160);

    expect(measureAoiRects()).toEqual([
      { code: "sau-click", xMin: 0.1, yMin: 0.1, xMax: 0.4, yMax: 0.3 },
    ]);
  });
});

describe("aoiRectsKey", () => {
  it("trả về chuỗi rỗng cho mảng rỗng", () => {
    expect(aoiRectsKey([])).toBe("");
  });

  it("ổn định khi thứ tự rect thay đổi", () => {
    const a = { code: "a", xMin: 0.1, yMin: 0.2, xMax: 0.3, yMax: 0.4 };
    const b = { code: "b", xMin: 0.5, yMin: 0.6, xMax: 0.7, yMax: 0.8 };

    expect(aoiRectsKey([a, b])).toBe(aoiRectsKey([b, a]));
  });

  it("làm tròn 4 chữ số thập phân", () => {
    const key = aoiRectsKey([
      { code: "x", xMin: 0.123456, yMin: 0.2, xMax: 0.3, yMax: 0.4 },
    ]);

    expect(key).toBe("x:0.1235,0.2000,0.3000,0.4000");
  });

  it("phân biệt rect khác code hoặc khác toạ độ", () => {
    const base = { code: "a", xMin: 0.1, yMin: 0.2, xMax: 0.3, yMax: 0.4 };

    expect(aoiRectsKey([base])).not.toBe(aoiRectsKey([{ ...base, code: "b" }]));
    expect(aoiRectsKey([base])).not.toBe(aoiRectsKey([{ ...base, xMax: 0.35 }]));
  });
});
