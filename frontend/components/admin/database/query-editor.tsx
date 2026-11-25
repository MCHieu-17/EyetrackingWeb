"use client";

import * as React from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";

interface QueryEditorProps {
  value: string;
  onChange: (value: string) => void;
  onRun: () => void;
  onCancel: () => void;
  isRunning: boolean;
  maxRows: number;
  onMaxRowsChange: (value: number) => void;
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
}

const ROW_OPTIONS = [50, 100, 200, 500];

export function QueryEditor({
  value,
  onChange,
  onRun,
  onCancel,
  isRunning,
  maxRows,
  onMaxRowsChange,
  textareaRef,
}: QueryEditorProps) {
  const gutterRef = React.useRef<HTMLDivElement | null>(null);
  const lineCount = Math.max(1, value.split("\n").length);
  const lineNumbers = Array.from({ length: lineCount }, (_, index) => index + 1);

  const handleScroll = () => {
    if (gutterRef.current && textareaRef.current) {
      gutterRef.current.scrollTop = textareaRef.current.scrollTop;
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      onRun();
      return;
    }
    if (event.key === "Tab") {
      event.preventDefault();
      const target = event.currentTarget;
      const start = target.selectionStart;
      const end = target.selectionEnd;
      onChange(`${value.slice(0, start)}  ${value.slice(end)}`);
      requestAnimationFrame(() => {
        target.selectionStart = start + 2;
        target.selectionEnd = start + 2;
      });
    }
  };

  return (
    <section className="rounded-[18px] border border-border bg-card shadow-xs">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="flex size-8 items-center justify-center rounded-full bg-accent text-accent-foreground">
            <Icon name="ri-code-line" className="size-4" />
          </span>
          <div>
            <p className="text-sm font-semibold">Câu lệnh SQL</p>
            <p className="text-xs text-muted-foreground">
              Chỉ SELECT/WITH · Ctrl/Cmd + Enter để chạy
            </p>
          </div>
        </div>
        <Badge variant="outline" className="gap-1">
          <Icon name="ri-lock-line" className="size-3" />
          Chỉ đọc
        </Badge>
      </div>

      <div className="relative">
        <div
          ref={gutterRef}
          aria-hidden
          className="pointer-events-none absolute inset-y-0 left-0 hidden w-10 select-none overflow-hidden border-r border-border bg-muted/40 py-3 text-right font-mono text-xs leading-6 text-muted-foreground sm:block"
        >
          {lineNumbers.map((line) => (
            <div key={line} className="pr-2">
              {line}
            </div>
          ))}
        </div>
        <label htmlFor="admin-db-sql" className="sr-only">
          Câu lệnh SQL
        </label>
        <textarea
          id="admin-db-sql"
          ref={textareaRef}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          onScroll={handleScroll}
          spellCheck={false}
          autoCapitalize="off"
          autoCorrect="off"
          aria-describedby="admin-db-sql-help"
          className="min-h-[220px] w-full resize-y bg-transparent py-3 pl-3 pr-4 font-mono text-sm leading-6 text-foreground outline-none placeholder:text-muted-foreground sm:pl-12"
          placeholder="SELECT * FROM users LIMIT 100;"
        />
        <p id="admin-db-sql-help" className="sr-only">
          Chỉ hỗ trợ câu lệnh SELECT hoặc WITH. Nhấn Ctrl hoặc Cmd cộng Enter để
          chạy.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-border px-4 py-3">
        <Button onClick={onRun} disabled={isRunning}>
          {isRunning ? <Spinner /> : <Icon name="ri-play-line" />}
          {isRunning ? "Đang chạy..." : "Chạy truy vấn"}
        </Button>
        {isRunning && (
          <Button variant="outline" onClick={onCancel}>
            <Icon name="ri-stop-line" />
            Hủy
          </Button>
        )}
        <Button
          variant="ghost"
          onClick={() => onChange("")}
          disabled={isRunning}
        >
          <Icon name="ri-delete-bin-line" />
          Xóa
        </Button>

        <div className="ml-auto flex items-center gap-2">
          <label
            htmlFor="admin-db-max-rows"
            className="text-xs text-muted-foreground"
          >
            Giới hạn dòng
          </label>
          <select
            id="admin-db-max-rows"
            value={maxRows}
            onChange={(event) => onMaxRowsChange(Number(event.target.value))}
            disabled={isRunning}
            className="h-9 rounded-full border border-border bg-surface px-3 text-sm text-foreground shadow-xs outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30 disabled:cursor-not-allowed disabled:opacity-55"
          >
            {ROW_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>
      </div>
    </section>
  );
}
