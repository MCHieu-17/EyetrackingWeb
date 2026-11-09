"use client";

import { type RefObject } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/utils";
import { getGazeStatus } from "./reader-helpers";

export function ReaderTopbar({
  courseTitle,
  preview,
  chatOpen,
  chatAllowed,
  chatReason,
  chatButtonRef,
  onToggleChat,
  gazeSource,
  calibrationRequired,
  onOpenMobileOutline,
}: {
  courseTitle: string;
  preview: boolean;
  chatOpen: boolean;
  chatAllowed: boolean;
  chatReason?: string | null;
  chatButtonRef?: RefObject<HTMLButtonElement | null>;
  onToggleChat: () => void;
  gazeSource: "real" | "off" | "simulated" | null;
  calibrationRequired: boolean;
  onOpenMobileOutline: () => void;
}) {
  const gazeStatus = getGazeStatus(gazeSource, calibrationRequired);

  return (
    <header
      data-aoi="header"
      className="z-40 flex h-12 shrink-0 items-center px-2 sm:px-3"
    >
      {preview ? (
        <span className="inline-flex min-w-0 items-center gap-2 rounded-full border border-border bg-white px-3 py-1.5 text-xs font-medium text-muted-foreground">
          <Icon name="ri-arrow-left-line" className="size-4 shrink-0" />
          <span className="hidden sm:inline">Khóa học của tôi</span>
        </span>
      ) : (
        <Link
          href="/student"
          className="inline-flex min-w-0 items-center gap-2 rounded-full border border-border bg-white px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:border-foreground/20 hover:text-foreground"
        >
          <Icon name="ri-arrow-left-line" className="size-4 shrink-0" />
          <span className="hidden sm:inline">Khóa học của tôi</span>
        </Link>
      )}

      <div className="mx-auto hidden min-w-0 px-4 md:block">
        <p className="max-w-[460px] truncate text-center text-xs font-medium text-muted-foreground">
          {courseTitle}
        </p>
      </div>

      <div className="ml-auto flex items-center gap-2">
        <Button
          ref={chatButtonRef}
          data-aoi="chat-open-button"
          variant="outline"
          size="sm"
          onClick={onToggleChat}
          title={
            chatReason ??
            (chatAllowed ? "Trợ lý học tập" : "Trợ lý đang khóa")
          }
          aria-expanded={chatOpen}
          aria-controls="assistant-panel"
          aria-label={chatOpen ? "Đóng trợ lý học tập" : "Mở trợ lý học tập"}
          className={cn(
            "gap-1.5",
            preview ? "inline-flex" : "hidden xl:inline-flex",
            chatOpen && "border-[#cfe0cb] bg-[#e8efe6] text-[#36533a]",
          )}
        >
          <Icon name="ri-sparkling-2-line" className="size-4" />
          <span className="hidden sm:inline">
            {!chatAllowed ? "Trợ lý đang khóa" : "Trợ lý"}
          </span>
        </Button>

        {!preview && gazeStatus === "active" ? (
          <div className="hidden items-center gap-1.5 rounded-full border border-border bg-white px-3 py-1.5 text-[11px] text-foreground sm:flex">
            <span className="size-1.5 animate-pulse rounded-full bg-primary" />
            Gaze đang hoạt động
          </div>
        ) : !preview && gazeStatus === "off" ? (
          <div className="hidden items-center gap-1.5 rounded-full border border-border bg-white px-3 py-1.5 text-[11px] text-muted-foreground sm:flex">
            <span className="size-1.5 rounded-full bg-muted-foreground" />
            Gaze tắt
          </div>
        ) : !preview ? (
          <div className="hidden items-center gap-1.5 rounded-full border border-border bg-white px-3 py-1.5 text-[11px] text-muted-foreground sm:flex">
            <span className="size-1.5 rounded-full bg-muted-foreground" />
            Gaze chưa kết nối
          </div>
        ) : null}

        <Button
          variant="ghost"
          size="icon-sm"
          className="lg:hidden"
          onClick={onOpenMobileOutline}
          aria-label="Mở mục lục"
        >
          <Icon name="ri-menu-line" className="size-5" />
        </Button>
      </div>
    </header>
  );
}
