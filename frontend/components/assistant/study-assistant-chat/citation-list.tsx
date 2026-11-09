"use client";

import { resolveMediaUrl } from "@/lib/api/client";
import type { ChatCitation } from "@/lib/api/chat";
import { LazyPdfPage } from "@/components/pdf/lazy-pdf-page";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { formatCitationLabel, formatCitationLocation } from "./chat-helpers";

function CitationChip({
  index,
  citation,
  onClick,
}: {
  index: number;
  citation: ChatCitation;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex max-w-full items-center truncate rounded-full border border-border bg-white px-2.5 py-1 text-[11px] font-medium text-muted-foreground transition hover:bg-muted hover:text-foreground"
      title={citation.title}
    >
      {formatCitationLabel(index, citation)}
    </button>
  );
}

export function CitationList({
  messageId,
  citations,
  onCitationClick,
}: {
  messageId: string;
  citations: ChatCitation[];
  onCitationClick: (citation: ChatCitation) => void;
}) {
  return (
    <div className="flex max-w-[92%] flex-wrap gap-1.5">
      {citations.map((citation, index) => (
        <CitationChip
          key={`${messageId}-${citation.documentId}-${index}`}
          index={index + 1}
          citation={citation}
          onClick={() => onCitationClick(citation)}
        />
      ))}
    </div>
  );
}

export function CitationDialog({
  citation,
  onClose,
}: {
  citation: ChatCitation | null;
  onClose: () => void;
}) {
  return (
    <Dialog open={Boolean(citation)} onOpenChange={(value) => !value && onClose()}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>{citation?.title ?? "Nguồn trích dẫn"}</DialogTitle>
          <DialogDescription>{formatCitationLocation(citation)}</DialogDescription>
        </DialogHeader>
        <div className="max-h-[60vh] overflow-auto px-6 pb-6">
          {(() => {
            const pdfUrl = resolveMediaUrl(citation?.pdfUrl);
            return pdfUrl ? (
              <LazyPdfPage
                url={pdfUrl}
                pageNumber={citation?.pageNumber ?? 1}
                alt={citation?.title ?? "Trang trích dẫn"}
                className="h-[55vh] w-full overflow-hidden rounded-xl border border-border bg-white"
              />
            ) : (
              <p className="rounded-xl border border-border bg-muted/40 p-4 text-sm text-muted-foreground">
                {citation?.snippet || "Không có ảnh slide cho nguồn này."}
              </p>
            );
          })()}
          {citation?.snippet && citation?.pdfUrl && (
            <p className="mt-3 text-xs leading-5 text-muted-foreground">
              {citation.snippet}
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
