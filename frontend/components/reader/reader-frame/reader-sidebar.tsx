"use client";

import { type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";

export function ReaderSidebar({
  desktopOpen,
  mobileOpen,
  onCloseMobile,
  outline,
}: {
  desktopOpen: boolean;
  mobileOpen: boolean;
  onCloseMobile: () => void;
  outline: ReactNode;
}) {
  return (
    <>
      {desktopOpen && (
        <aside
          data-aoi="outline"
          className="hidden w-[220px] shrink-0 flex-col overflow-hidden rounded-[20px] border border-border/80 bg-white shadow-xs lg:flex"
        >
          {outline}
        </aside>
      )}

      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-black/35 backdrop-blur-[2px]"
            onClick={onCloseMobile}
            aria-label="Đóng mục lục"
          />
          <aside
            data-aoi="outline"
            className="absolute inset-y-2 left-2 flex w-[min(88vw,320px)] flex-col overflow-hidden rounded-[20px] border border-border/80 bg-white shadow-lg"
          >
            <div className="flex h-14 items-center justify-between px-5">
              <span className="text-sm font-semibold">Mục lục</span>
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={onCloseMobile}
                aria-label="Đóng mục lục"
              >
                <Icon name="ri-close-line" className="size-5" />
              </Button>
            </div>
            {outline}
          </aside>
        </div>
      )}
    </>
  );
}
