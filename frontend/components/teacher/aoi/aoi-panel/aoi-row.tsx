"use client";

import { useRef, useState } from "react";
import { Icon } from "@/components/ui/icon";
import type { AoiDefinitionInput } from "@/lib/api/aoi";
import { colorFor } from "@/lib/aoi/colors";
import { cn } from "@/lib/utils";

export function AoiRow({
  definition,
  selected,
  hovered,
  inactive,
  canManage,
  subtitle,
  icon,
  labelValue,
  labelPrefix,
  onLabelChange,
  onSelect,
  onHover,
  onRename,
  onDeactivate,
  onRestore,
  onDelete,
}: {
  definition: AoiDefinitionInput;
  selected: boolean;
  hovered: boolean;
  inactive?: boolean;
  canManage: boolean;
  subtitle?: string;
  icon: string;
  labelValue?: string | null;
  labelPrefix?: string;
  onLabelChange?: (label: string) => string | null;
  onSelect: () => void;
  onHover: (value: boolean) => void;
  onRename: (name: string) => void;
  onDeactivate?: () => void;
  onRestore?: () => void;
  onDelete?: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  // null = chưa sửa, hiển thị nhãn hiện tại từ props.
  const [labelDraft, setLabelDraft] = useState<string | null>(null);
  const [labelError, setLabelError] = useState<string | null>(null);
  const skipLabelCommitRef = useRef(false);
  const color = inactive ? "var(--muted-foreground)" : colorFor(definition.code);
  const labelText = labelDraft ?? labelValue ?? "";
  const labelInputId = `aoi-label-${definition.code}`;

  const commitLabel = () => {
    if (!onLabelChange || labelDraft === null) return null;
    const error = onLabelChange(labelDraft);
    setLabelError(error);
    if (!error) setLabelDraft(null);
    return error;
  };

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
          ? "border-primary/30 bg-accent"
          : hovered
            ? "border-border bg-muted"
            : "border-transparent hover:border-border hover:bg-muted",
        inactive && "opacity-55",
      )}
    >
      <div className="flex items-center gap-2">
        <span
          className="size-2.5 shrink-0 rounded-full"
          style={{ backgroundColor: color }}
        />
        <Icon name={icon} className="size-3.5 shrink-0 text-muted-foreground" />
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
            className="w-full truncate rounded-md border border-transparent bg-transparent px-1 py-0.5 text-xs font-medium text-foreground outline-none transition-colors hover:border-border focus:border-primary/30 focus:bg-card focus:ring-2 focus:ring-ring/25"
          />
          {inactive ? (
            <p className="truncate px-1 text-[10px] text-muted-foreground">
              Chưa đánh dấu{subtitle ? ` · ${subtitle}` : ""}
            </p>
          ) : subtitle ? (
            <p className="truncate px-1 text-[10px] text-muted-foreground">{subtitle}</p>
          ) : null}
          {onLabelChange && (
            <div className="mt-1" onClick={(event) => event.stopPropagation()}>
              <div className="flex items-center gap-1">
                <label
                  htmlFor={labelInputId}
                  className="shrink-0 text-[10px] text-muted-foreground"
                >
                  Nhãn phân tích
                </label>
                <span className="shrink-0 rounded bg-muted px-1 py-0.5 font-mono text-[10px] text-muted-foreground">
                  {labelPrefix ?? ""}
                </span>
                <input
                  id={labelInputId}
                  value={labelText}
                  onChange={(event) => {
                    setLabelDraft(event.target.value);
                    setLabelError(null);
                  }}
                  onBlur={() => {
                    if (skipLabelCommitRef.current) {
                      skipLabelCommitRef.current = false;
                      return;
                    }
                    commitLabel();
                  }}
                  onKeyDown={(event) => {
                    event.stopPropagation();
                    if (event.key === "Enter") {
                      event.preventDefault();
                      if (!commitLabel()) {
                        skipLabelCommitRef.current = true;
                        event.currentTarget.blur();
                      }
                    } else if (event.key === "Escape") {
                      event.preventDefault();
                      skipLabelCommitRef.current = true;
                      setLabelDraft(null);
                      setLabelError(null);
                      event.currentTarget.blur();
                    }
                  }}
                  readOnly={!canManage}
                  maxLength={64}
                  placeholder="AOI_THANHCHAT"
                  aria-label="Nhãn phân tích"
                  className="min-w-0 flex-1 rounded-md border border-border bg-card/70 px-1.5 py-0.5 font-mono text-[10px] text-foreground outline-none transition-colors hover:border-primary/30 focus:border-primary/40 focus:bg-card focus:ring-2 focus:ring-ring/25"
                />
              </div>
              {labelError && (
                <p
                  role="alert"
                  className="mt-0.5 pl-1 text-[10px] leading-4 text-destructive"
                >
                  {labelError}
                </p>
              )}
            </div>
          )}
        </div>
        {inactive && onRestore && canManage && (
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onRestore();
            }}
            className="flex size-6 shrink-0 items-center justify-center rounded-full text-primary transition-colors hover:bg-accent"
            aria-label="Bật lại vùng"
            title="Bật lại vùng"
          >
            <Icon name="ri-arrow-go-back-line" className="size-3.5" />
          </button>
        )}
        {onDelete && canManage && (
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              setConfirming(true);
            }}
            className="flex size-6 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
            aria-label="Xóa vùng"
            title="Xóa vùng"
          >
            <Icon name="ri-delete-bin-line" className="size-3.5" />
          </button>
        )}
        {!inactive && onDeactivate && canManage && (
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onDeactivate();
            }}
            className="flex size-6 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-muted-foreground"
            aria-label="Bỏ đánh dấu vùng"
            title="Bỏ đánh dấu vùng"
          >
            <Icon name="ri-subtract-line" className="size-3.5" />
          </button>
        )}
      </div>

      {confirming && onDelete && (
        <div className="mt-1.5 flex items-center gap-2 rounded-lg bg-card px-2 py-1.5 text-[11px]">
          <span className="min-w-0 flex-1 text-muted-foreground">Xóa vùng này?</span>
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
            className="text-muted-foreground"
          >
            Hủy
          </button>
        </div>
      )}
    </div>
  );
}
