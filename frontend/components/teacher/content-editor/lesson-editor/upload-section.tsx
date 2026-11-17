"use client";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/utils";
import type { SlideAdmin } from "@/lib/types/domain";
import { UploadAlerts } from "./upload-alerts";
import type { UploadState } from "./upload-helpers";

/** Khối tải tài liệu: nút chọn file, vùng kéo thả và các cảnh báo index. */
export function UploadSection({
  limitsHint,
  canManage,
  uploading,
  hasSlides,
  slideCount,
  dragOver,
  upload,
  lastFile,
  slidesError,
  pendingSlides,
  unindexedSlides,
  reindexing,
  reindexError,
  onOpenFileDialog,
  onDragOver,
  onDragLeave,
  onDrop,
  onRetry,
  onChooseFile,
  onRetryIndex,
}: {
  limitsHint: string;
  canManage: boolean;
  uploading: boolean;
  hasSlides: boolean;
  slideCount: number;
  dragOver: boolean;
  upload: UploadState;
  lastFile: File | null;
  slidesError: boolean;
  pendingSlides: SlideAdmin[];
  unindexedSlides: SlideAdmin[];
  reindexing: boolean;
  reindexError: string;
  onOpenFileDialog: () => void;
  onDragOver: () => void;
  onDragLeave: () => void;
  onDrop: (files: FileList) => void;
  onRetry: () => void;
  onChooseFile: () => void;
  onRetryIndex: () => void;
}) {
  return (
    <section className="rounded-[20px] border border-[#eeeee9] bg-white p-4 shadow-xs sm:p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h3 className="text-base font-semibold text-black">Tài liệu bài giảng</h3>
          <p className="mt-1 text-sm leading-6 text-black/65">
            {hasSlides
              ? `Đang dùng ${slideCount} trang slide. Tải tài liệu mới để tạo lại toàn bộ.`
              : "Tải PDF/PPTX/PPT/ODP lên để tạo slide cho bài giảng này."}
          </p>
          <p className="mt-1 text-xs leading-5 text-black/55">{limitsHint}</p>
        </div>
        {canManage && (
          <Button
            type="button"
            variant="outline"
            className="shrink-0 rounded-full border-black/10 bg-white"
            onClick={onOpenFileDialog}
            disabled={uploading}
          >
            <Icon
              name={uploading ? "ri-loader-4-line" : "ri-upload-cloud-2-line"}
              className={cn("size-4", uploading && "animate-spin")}
            />
            {uploading ? "Đang xử lý…" : hasSlides ? "Thay tài liệu" : "Chọn tài liệu"}
          </Button>
        )}
      </div>

      {canManage && (
        <button
          type="button"
          onClick={onOpenFileDialog}
          onDragOver={(event) => {
            event.preventDefault();
            onDragOver();
          }}
          onDragLeave={onDragLeave}
          onDrop={(event) => {
            event.preventDefault();
            onDragLeave();
            onDrop(event.dataTransfer.files);
          }}
          className={cn(
            "mt-4 flex w-full flex-col items-center justify-center gap-1 rounded-[18px] border border-dashed px-4 py-6 text-center transition",
            uploading
              ? "border-[#cfdcca] bg-[#e8f1e6]/70"
              : "border-[#cfdcca] bg-[#e8f1e6]/55 hover:bg-[#e8f1e6]",
            dragOver && "border-[#6f8f69] bg-[#e8f1e6]",
          )}
        >
          {upload.status === "uploading" ? (
            <>
              <Icon name="ri-loader-4-line" className="size-6 animate-spin text-[#52704f]" />
              <span className="mt-1 text-sm font-medium text-black">
                Đang tải và xử lý “{upload.fileName}”…
              </span>
              <span className="text-xs text-black/60">
                PPTX/PPT/ODP được chuyển sang PDF; file nhiều trang có thể mất
                1–2 phút. Vui lòng không đóng trang.
              </span>
            </>
          ) : (
            <>
              <Icon name="ri-file-text-line" className="size-6 text-muted-foreground" />
              <span className="mt-1 text-sm font-medium text-black">
                {hasSlides
                  ? "Kéo tài liệu mới vào đây hoặc bấm để chọn"
                  : "Kéo PDF/PPTX/PPT/ODP vào đây hoặc bấm để chọn"}
              </span>
              <span className="text-xs text-black/55">{limitsHint}</span>
            </>
          )}
        </button>
      )}

      <UploadAlerts
        upload={upload}
        lastFile={lastFile}
        slidesError={slidesError}
        pendingSlides={pendingSlides}
        unindexedSlides={unindexedSlides}
        reindexing={reindexing}
        reindexError={reindexError}
        onRetry={onRetry}
        onChooseFile={onChooseFile}
        onRetryIndex={onRetryIndex}
      />
    </section>
  );
}
