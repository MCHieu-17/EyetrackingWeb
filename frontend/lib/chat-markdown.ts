import type { Root, Text, Link } from "mdast";
import { visit } from "unist-util-visit";

// Protect code before normalizing the alternate LaTeX delimiters.
export function normalizeMath(text: string): string {
  return text.split(/(```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]*`)/g).map((part, i) =>
    i % 2 ? part : part.replace(/\\\[([\s\S]*?)\\\]/g, (_, math: string) => `\n$$${math}$$\n`)
      .replace(/\\\(([\s\S]*?)\\\)/g, (_, math: string) => `$${math}$`),
  ).join("");
}

export function remarkCitations({ messageId, count }: { messageId: string; count: number }) {
  return (tree: Root) => {
    visit(tree, "text", (node: Text, index, parent) => {
      if (!parent || index === undefined || parent.type === "link" || parent.type === "linkReference") return;
      const parts: (Text | Link)[] = [];
      let start = 0;
      for (const match of node.value.matchAll(/\[(\d+)\]/g)) {
        const n = Number(match[1]);
        if (n < 1 || n > count) continue;
        parts.push({ type: "text", value: node.value.slice(start, match.index) });
        parts.push({ type: "link", url: `#chat-cite-${messageId}-${n}`, children: [{ type: "text", value: match[0] }] });
        start = match.index! + match[0].length;
      }
      if (!parts.length) return;
      parts.push({ type: "text", value: node.value.slice(start) });
      parent.children.splice(index, 1, ...parts);
      return index + parts.length;
    });
  };
}
