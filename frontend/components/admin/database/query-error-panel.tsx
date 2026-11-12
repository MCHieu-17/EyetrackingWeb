"use client";

import * as React from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import type { AdminDbQueryErrorDetail } from "@/lib/api/admin-db";
import { ApiError } from "@/lib/api/client";
import { copyText } from "@/lib/admin-db";

interface QueryErrorPanelProps {
  error: ApiError | null;
}

export function QueryErrorPanel({ error }: QueryErrorPanelProps) {
  const detail = React.useMemo<AdminDbQueryErrorDetail | null>(() => {
    if (!error || !error.detail || typeof error.detail !== "object") {
      return null;
    }
    const payload = error.detail as { detail?: unknown };
    if (
      payload.detail &&
      typeof payload.detail === "object" &&
      !Array.isArray(payload.detail)
    ) {
      return payload.detail as AdminDbQueryErrorDetail;
    }
    return null;
  }, [error]);

  const errorText = React.useMemo(() => {
    if (!error) return "";
    if (!detail) return error.message;
    return [
      error.message,
      detail.code ? `Mã lỗi: ${detail.code}` : "",
      detail.detail ? `Chi tiết: ${detail.detail}` : "",
      detail.hint ? `Gợi ý: ${detail.hint}` : "",
    ]
      .filter(Boolean)
      .join("\n");
  }, [error, detail]);

  if (!error) return null;

  return (
    <Alert variant="destructive" title="Không chạy được truy vấn">
      <p>{error.message}</p>
      {detail && (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs font-medium text-foreground">
            Chi tiết lỗi
          </summary>
          <div className="mt-2 space-y-1 font-mono text-[11px]">
            {detail.code && <p>Mã lỗi: {detail.code}</p>}
            {detail.position != null && <p>Vị trí: {detail.position}</p>}
            {detail.detail && (
              <p className="whitespace-pre-wrap break-words">
                Chi tiết: {detail.detail}
              </p>
            )}
            {detail.hint && (
              <p className="whitespace-pre-wrap break-words">
                Gợi ý: {detail.hint}
              </p>
            )}
          </div>
        </details>
      )}
      <div className="mt-3">
        <Button
          variant="outline"
          size="xs"
          onClick={() => void copyText(errorText)}
        >
          <Icon name="ri-file-copy-line" />
          Sao chép lỗi
        </Button>
      </div>
    </Alert>
  );
}
