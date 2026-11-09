"use client";

import { useState } from "react";
import { Icon } from "@/components/ui/icon";
import type { AoiDefinitionInput } from "@/lib/api/aoi";
import { colorFor } from "@/lib/aoi/colors";
import { cn } from "@/lib/utils";

export function AoiRow({
  definition,
  selected,
  hovered,
  hidden,
  inactive,
  canManage,
  subtitle,
  icon,
  onSelect,
  onHover,
  onRename,
  onDeactivate,
  onRestore,
  onDelete,
  onToggleHidden,
}: {
  definition: AoiDefinitionInput;
  selected: boolean;
  hovered: boolean;
  hidden: boolean;
  inactive?: boolean;
  canManage: boolean;
  subtitle?: string;
  icon: string;
  onSelect: () => void;
  onHover: (value: boolean) => void;
  onRename: (name: string) => void;
  onDeactivate?: () => void;
  onRestore?: () => void;
  onDelete?: () => void;
  onToggleHidden: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const color = inactive ? "#9ca3af" : colorFor(definition.code);

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect();
        }
      }}
      onMouseEnter={() => onHover(true)}
      onMouseLeave={() => onHover(false)}
      className={cn(
        "group rounded-xl border px-2.5 py-2 transition-colors",
        selected
          ? "border-[#36533a]/30 bg-[#e8f1e6]"
          : hovered
            ? "border-black/10 bg-[#f7f7f4]"
            : "border-transparent hover:border-black/10 hover:bg-[#f7f7f4]",
        (hidden || inactive) && "opacity-55",
      )}
    >
      <div className="flex items-center gap-2">
        <span
          className="size-2.5 shrink-0 rounded-full"
          style={{ backgroundColor: color }}
        />
        <Icon name={icon} className="size-3.5 shrink-0 text-black/45" />
        <div className="min-w-0 flex-1">
          <input
            value={definition.name}
            onChange={(event) => onRename(event.target.value)}
            onClick={(event) => event.stopPropagation()}
            onKeyDown={(event) => {
              if (event.key === "Enter") event.currentTarget.blur();
              if (event.key === "Escape") {
                event.currentTarget.value = definition.name;
                event.currentTarget.blur();
              }
            }}
            readOnly={!canManage}
            aria-label="Tên vùng"
            className="w-full truncate rounded-md border border-transparent bg-transparent px-1 py-0.5 text-xs font-medium text-black outline-none transition-colors hover:border-black/10 focus:border-black/20 focus:bg-white focus:ring-2 focus:ring-[#e8f1e6]"
          />
          {inactive ? (
            <p className="truncate px-1 text-[10px] text-black/45">
              Chưa đánh dấu
            </p>
          ) : subtitle ? (
            <p className="truncate px-1 text-[10px] text-black/45">{subtitle}</p>
          ) : null}
        </div>
        {!inactive && (
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onToggleHidden();
            }}
            className="flex size-6 shrink-0 items-center justify-center rounded-full text-black/35 transition-colors hover:bg-white hover:text-black/70"
            aria-label={hidden ? "Hiện vùng" : "Ẩn vùng"}
            title={hidden ? "Hiện vùng" : "Ẩn vùng"}
          >
            <Icon
              name={hidden ? "ri-eye-off-line" : "ri-eye-line"}
              className="size-3.5"
            />
          </button>
        )}
        {inactive && onRestore && canManage && (
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onRestore();
            }}
            className="flex size-6 shrink-0 items-center justify-center rounded-full text-[#36533a] transition-colors hover:bg-[#e8f1e6]"
            aria-label="Bật lại vùng"
            title="Bật lại vùng"
          >
            <Icon name="ri-arrow-go-back-line" className="size-3.5" />
          </button>
        )}
        {!inactive && onDeactivate && canManage && (
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onDeactivate();
            }}
            className="flex size-6 shrink-0 items-center justify-center rounded-full text-black/35 transition-colors hover:bg-black/5 hover:text-black/70"
            aria-label="Bỏ đánh dấu vùng"
            title="Bỏ đánh dấu vùng"
          >
            <Icon name="ri-subtract-line" className="size-3.5" />
          </button>
        )}
        {!inactive && onDelete && canManage && (
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              setConfirming(true);
            }}
            className="flex size-6 shrink-0 items-center justify-center rounded-full text-black/35 transition-colors hover:bg-destructive/10 hover:text-destructive"
            aria-label="Xóa vùng"
            title="Xóa vùng"
          >
            <Icon name="ri-delete-bin-line" className="size-3.5" />
          </button>
        )}
      </div>

      {confirming && onDelete && (
        <div className="mt-1.5 flex items-center gap-2 rounded-lg bg-white px-2 py-1.5 text-[11px]">
          <span className="min-w-0 flex-1 text-black/60">Xóa vùng này?</span>
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onDelete?.();
              setConfirming(false);
            }}
            className="font-semibold text-destructive"
          >
            Xóa
          </button>
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              setConfirming(false);
            }}
            className="text-black/50"
          >
            Hủy
          </button>
        </div>
      )}
    </div>
  );
}
