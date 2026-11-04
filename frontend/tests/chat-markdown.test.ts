import { describe, it, expect } from "vitest";
import { unified } from "unified";
import remarkParse from "remark-parse";
import remarkMath from "remark-math";
import { normalizeMath, remarkCitations } from "@/lib/chat-markdown";

describe("chat rich text", () => {
  it("normalizes alternate math without changing code", () => {
    expect(normalizeMath('\\(x^2\\) and \\[y\\] `\\(code\\)`')).toBe('$x^2$ and \n$$y$$\n `\\(code\\)`');
  });
  it("only links real citations in prose", () => {
    const processor = unified().use(remarkParse).use(remarkMath).use(remarkCitations, { messageId: "m", count: 1 });
    const tree = processor.runSync(processor.parse('Source [1]. $a[1]$ `v[1]` [existing](https://example.com)'));
    const json = JSON.stringify(tree);
    expect(json.match(/#chat-cite-m-1/g)).toHaveLength(1);
    expect(json).toContain('a[1]');
    expect(json).toContain('v[1]');
  });
});
