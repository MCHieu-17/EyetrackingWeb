import type { Paragraph, Root } from "mdast";
import { describe, expect, it } from "vitest";

import { normalizeMath, remarkCitations } from "@/lib/chat-markdown";

describe("normalizeMath", () => {
  it("đổi \\[...\\] thành $$...$$", () => {
    expect(normalizeMath("trước \\[x^2\\] sau")).toBe("trước \n$$x^2$$\n sau");
  });

  it("đổi \\(...\\) thành $...$", () => {
    expect(normalizeMath("trước \\(x^2\\) sau")).toBe("trước $x^2$ sau");
  });

  it("xử lý nhiều công thức trong cùng chuỗi", () => {
    expect(normalizeMath("\\(a\\) và \\[b\\]")).toBe("$a$ và \n$$b$$\n");
  });

  it("giữ nguyên công thức nhiều dòng", () => {
    expect(normalizeMath("\\[\na + b\n\\]")).toBe("\n$$\na + b\n$$\n");
  });

  it("không đụng vào code fence", () => {
    const text = "```\n\\[x\\]\n```";

    expect(normalizeMath(text)).toBe(text);
  });

  it("không đụng vào code fence dùng ~~~", () => {
    const text = "~~~\n\\(x\\)\n~~~";

    expect(normalizeMath(text)).toBe(text);
  });

  it("không đụng vào inline code", () => {
    const text = "`\\[x\\]` và `\\(y\\)`";

    expect(normalizeMath(text)).toBe(text);
  });

  it("giữ nguyên văn bản thường", () => {
    expect(normalizeMath("không có công thức")).toBe("không có công thức");
  });
});

describe("remarkCitations", () => {
  function paragraphTree(value: string): Root {
    return {
      type: "root",
      children: [{ type: "paragraph", children: [{ type: "text", value }] }],
    };
  }

  it("biến citation trong khoảng count thành link", () => {
    const tree = paragraphTree("Xem [1] và [3].");

    remarkCitations({ messageId: "m1", count: 2 })(tree);

    const paragraph = tree.children[0] as Paragraph;
    expect(paragraph.children).toEqual([
      { type: "text", value: "Xem " },
      {
        type: "link",
        url: "#chat-cite-m1-1",
        children: [{ type: "text", value: "[1]" }],
      },
      { type: "text", value: " và [3]." },
    ]);
  });

  it("không đổi gì khi count = 0", () => {
    const tree = paragraphTree("Xem [1].");

    remarkCitations({ messageId: "m1", count: 0 })(tree);

    expect(tree).toEqual(paragraphTree("Xem [1]."));
  });

  it("bỏ qua citation nằm trong link", () => {
    const tree: Root = {
      type: "root",
      children: [
        {
          type: "paragraph",
          children: [
            {
              type: "link",
              url: "https://example.com",
              children: [{ type: "text", value: "[1]" }],
            },
          ],
        },
      ],
    };

    remarkCitations({ messageId: "m1", count: 5 })(tree);

    expect(tree).toEqual({
      type: "root",
      children: [
        {
          type: "paragraph",
          children: [
            {
              type: "link",
              url: "https://example.com",
              children: [{ type: "text", value: "[1]" }],
            },
          ],
        },
      ],
    });
  });
});
