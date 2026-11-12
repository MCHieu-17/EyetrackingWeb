"use client";

import * as React from "react";
import { Badge } from "@/components/ui/badge";
import type { AdminDbResultColumn } from "@/lib/api/admin-db";
import {
  formatCellValue,
  shortTypeLabel,
  truncateText,
} from "@/lib/admin-db";
import { cn } from "@/lib/utils";
import { CellDialog, type SelectedCell } from "./cell-dialog";

interface DataTableProps {
  columns: AdminDbResultColumn[];
  rows: unknown[][];
  caption?: string;
}

export function DataTable({
  columns,
  rows,
  caption = "Kết quả truy vấn",
}: DataTableProps) {
  const [selectedCell, setSelectedCell] = React.useState<SelectedCell | null>(
    null,
  );

  return (
    <>
      <div className="max-h-[60vh] overflow-auto rounded-[14px] border border-[#eeeee9]">
        <table className="w-full border-collapse text-left text-xs">
          <caption className="sr-only">{caption}</caption>
          <thead className="sticky top-0 z-10 bg-[#f7f7f4]">
            <tr>
              <th className="w-10 border-b border-[#eeeee9] px-2 py-2 text-right font-mono text-[10px] font-semibold text-muted-foreground">
                #
              </th>
              {columns.map((column, index) => (
                <th
                  key={`${column.name}-${index}`}
                  className="border-b border-[#eeeee9] px-3 py-2 text-left font-semibold text-foreground"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[11px]">
                      {column.name}
                    </span>
                    <span
                      className="rounded-full bg-muted px-1.5 py-0.5 font-mono text-[9px] font-normal text-muted-foreground"
                      title={column.type}
                    >
                      {shortTypeLabel(column.type)}
                    </span>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr
                key={rowIndex}
                className="odd:bg-white even:bg-[#fafaf7] hover:bg-accent/30"
              >
                <td className="border-b border-[#f0f1ec] px-2 py-1.5 text-right font-mono text-[10px] text-muted-foreground">
                  {rowIndex + 1}
                </td>
                {columns.map((column, columnIndex) => {
                  const cell = formatCellValue(row[columnIndex], column.type);
                  return (
                    <td
                      key={`${rowIndex}-${columnIndex}`}
                      className="max-w-[320px] border-b border-[#f0f1ec] px-3 py-1.5 align-top"
                    >
                      <button
                        type="button"
                        onClick={() =>
                          setSelectedCell({
                            column,
                            value: row[columnIndex],
                          })
                        }
                        className="block w-full truncate text-left"
                        title={truncateText(cell.fullText)}
                      >
                        {cell.kind === "null" ? (
                          <span className="italic text-muted-foreground">
                            NULL
                          </span>
                        ) : cell.kind === "boolean" ? (
                          <Badge
                            variant={
                              cell.text === "true" ? "success" : "secondary"
                            }
                          >
                            {cell.text}
                          </Badge>
                        ) : (
                          <span
                            className={cn(
                              "font-mono",
                              cell.kind === "number" && "tabular-nums",
                            )}
                          >
                            {cell.text}
                          </span>
                        )}
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <CellDialog
        cell={selectedCell}
        onOpenChange={(open) => {
          if (!open) setSelectedCell(null);
        }}
      />
    </>
  );
}
