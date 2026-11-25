"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Icon } from "@/components/ui/icon";
import type { AdminDbResultColumn } from "@/lib/api/admin-db";
import { cellToText, copyText } from "@/lib/admin-db";

export interface SelectedCell {
  column: AdminDbResultColumn;
  value: unknown;
}

interface CellDialogProps {
  cell: SelectedCell | null;
  onOpenChange: (open: boolean) => void;
}

export function CellDialog({ cell, onOpenChange }: CellDialogProps) {
  const [copied, setCopied] = React.useState(false);
  const text = cell ? cellToText(cell.value) : "";

  const handleOpenChange = (open: boolean) => {
    if (!open) setCopied(false);
    onOpenChange(open);
  };

  return (
    <Dialog open={cell !== null} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="font-mono text-base">
            {cell?.column.name}
          </DialogTitle>
          <DialogDescription>{cell?.column.type}</DialogDescription>
        </DialogHeader>
        <div className="max-h-[60vh] overflow-auto px-6 pb-4">
          <pre className="whitespace-pre-wrap break-words rounded-xl bg-muted p-4 font-mono text-xs text-foreground">
            {text}
          </pre>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={async () => {
              const ok = await copyText(text);
              setCopied(ok);
            }}
          >
            <Icon name={copied ? "ri-check-line" : "ri-file-copy-line"} />
            {copied ? "Đã sao chép" : "Sao chép"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
