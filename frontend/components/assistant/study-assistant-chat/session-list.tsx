"use client";

import {
  RiAddLine,
  RiChatHistoryLine,
  RiDeleteBinLine,
  RiEditLine,
} from "@remixicon/react";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { ChatSessionLike } from "./chat-helpers";

export function SessionMenu({
  sessions,
  currentSession,
  onSelectSession,
  onRename,
  onDelete,
}: {
  sessions: ChatSessionLike[];
  currentSession: ChatSessionLike | undefined;
  onSelectSession: (sessionId: string | null) => void;
  onRename: () => void;
  onDelete: () => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Lịch sử phiên chat">
          <RiChatHistoryLine className="size-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-72">
        <DropdownMenuLabel>Phiên chat</DropdownMenuLabel>
        <DropdownMenuItem onSelect={() => onSelectSession(null)}>
          <RiAddLine className="mr-2 size-4" />
          Phiên mới
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        {sessions.length === 0 && (
          <p className="px-2 py-3 text-xs text-muted-foreground">Chưa có phiên nào.</p>
        )}
        {sessions.map((session) => (
          <DropdownMenuItem
            key={session.id}
            disabled={session.canContinue === false}
            onSelect={() => onSelectSession(session.id)}
            className="flex items-center justify-between gap-2"
          >
            <span className="min-w-0 flex-1 truncate">{session.title}</span>
            <span className="text-[10px] text-muted-foreground">
              {session.messageCount}
            </span>
          </DropdownMenuItem>
        ))}
        {currentSession && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={onRename}>
              <RiEditLine className="mr-2 size-4" />
              Đổi tên phiên
            </DropdownMenuItem>
            <DropdownMenuItem
              onSelect={onDelete}
              className="text-destructive focus:text-destructive"
            >
              <RiDeleteBinLine className="mr-2 size-4" />
              Xoá phiên
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function RenameSessionDialog({
  open,
  onOpenChange,
  value,
  onValueChange,
  onConfirm,
  pending,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  value: string;
  onValueChange: (value: string) => void;
  onConfirm: () => void;
  pending: boolean;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Đổi tên phiên chat</DialogTitle>
        </DialogHeader>
        <div className="px-6 pb-4">
          <Textarea
            value={value}
            onChange={(event) => onValueChange(event.target.value)}
            rows={2}
            maxLength={255}
          />
        </div>
        <div className="flex justify-end gap-2 border-t border-border p-4">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Hủy
          </Button>
          <Button onClick={onConfirm} disabled={!value.trim() || pending}>
            Lưu
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function DeleteSessionDialog({
  open,
  onOpenChange,
  onConfirm,
  loading,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  loading: boolean;
}) {
  return (
    <ConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Xoá phiên chat?"
      description="Toàn bộ tin nhắn trong phiên này sẽ bị xoá và không thể khôi phục."
      confirmLabel="Xoá"
      destructive
      loading={loading}
      onConfirm={onConfirm}
    />
  );
}
