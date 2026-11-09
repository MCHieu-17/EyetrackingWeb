"use client";

import "katex/dist/katex.min.css";
import { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { normalizeMath, remarkCitations } from "@/lib/chat-markdown";
import { cn } from "@/lib/utils";
import type { ChatCitation } from "@/lib/api/chat";

const MARKDOWN_CLASS = cn(
  "text-sm leading-6 break-words",
  "[&_p]:my-1.5 [&_strong]:font-semibold [&_em]:italic",
  "[&_ul]:my-1.5 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:my-1.5 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:my-0.5",
  "[&_h1]:mt-3 [&_h1]:text-base [&_h1]:font-semibold [&_h2]:mt-3 [&_h2]:text-sm [&_h2]:font-semibold [&_h3]:mt-2 [&_h3]:font-semibold",
  "[&_code]:rounded [&_code]:bg-black/5 [&_code]:px-1 [&_code]:py-0.5 [&_code]:text-[0.85em]",
  "[&_pre]:my-2 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-neutral-900 [&_pre]:p-3 [&_pre]:text-xs [&_pre]:text-white",
  "[&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_pre_code]:text-inherit",
  "[&_table]:my-2 [&_table]:w-full [&_table]:border-collapse [&_table]:text-xs",
  "[&_th]:border [&_th]:border-border [&_th]:bg-muted [&_th]:px-2 [&_th]:py-1 [&_th]:text-left",
  "[&_td]:border [&_td]:border-border [&_td]:px-2 [&_td]:py-1",
  "[&_blockquote]:border-l-2 [&_blockquote]:border-border [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground",
  "[&_hr]:my-3 [&_img]:max-w-full [&_img]:rounded-lg",
  "[&_a]:font-medium [&_a]:text-[#36533a] [&_a]:underline [&_a]:underline-offset-2",
);

export const Markdown = memo(function Markdown({
  text,
  messageId,
  citations,
  onCitationClick,
}: {
  text: string;
  messageId: string;
  citations: ChatCitation[];
  onCitationClick: (citation: ChatCitation) => void;
}) {
  return (
    <div className={MARKDOWN_CLASS}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath, [remarkCitations, { messageId, count: citations.length }]]}
        rehypePlugins={[[rehypeKatex, { trust: false, throwOnError: false }]]}
        skipHtml
        components={{
          table: ({ children }) => <div className="max-w-full overflow-x-auto"><table>{children}</table></div>,
          a: ({ href, children }) => {
            if (href?.startsWith("#chat-cite-")) {
              const index = Number(href.split("-").pop());
              const citation = citations[index - 1];
              if (citation) {
                return (
                  <button
                    type="button"
                    className="mx-0.5 inline-flex min-w-4 items-center justify-center rounded border border-current px-1 text-[10px] align-super font-semibold"
                    onClick={() => onCitationClick(citation)}
                    aria-label={`Xem nguồn trích dẫn ${index}`}
                  >
                    {children}
                  </button>
                );
              }
            }
            return (
              <a href={href} target="_blank" rel="noreferrer">
                {children}
              </a>
            );
          },
        }}
      >
        {normalizeMath(text)}
      </ReactMarkdown>
    </div>
  );
});
