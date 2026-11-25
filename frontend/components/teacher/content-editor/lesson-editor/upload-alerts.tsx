"use client";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/utils";
import type { SlideAdmin } from "@/lib/types/domain";
import type { UploadState } from "./upload-helpers";

/** Các thông báo trạng thái tải/index tài liệu của bài giảng. */
export function UploadAlerts({
  upload,
  lastFile,
  slidesError,
  pendingSlides,
  unindexedSlides,
  reindexing,
  reindexError,
  onRetry,
  onChooseFile,
  onRetryIndex,
}: {
  upload: UploadState;
  lastFile: File | null;
  slidesError: boolean;
  pendingSlides: SlideAdmin[];
  unindexedSlides: SlideAdmin[];
  reindexing: boolean;
  reindexError: string;
  onRetry: () => void;
  onChooseFile: () => void;
  onRetryIndex: () => void;
}) {
  return (
    <>
      {upload.status === "success" && (
        <Alert
          variant="success"
          className="mt-3"
          title={`Đã tạo ${upload.pages} trang slide từ "${upload.fileName}".`}
        >
          Kiểm tra lưới trang bên dưới trước khi giao bài cho học viên.
        </Alert>
      )}

      {upload.status === "error" && (
        <Alert variant="destructive" className="mt-3" title="Không tải được tài liệu">
          <p>{upload.message}</p>
          <p className="mt-1 text-xs text-muted-foreground">
            File “{upload.fileName}” vẫn được giữ — bạn có thể thử lại hoặc chọn file khác.
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {lastFile && (
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="rounded-full border-border bg-card"
                onClick={onRetry}
              >
                <Icon name="ri-refresh-line" className="size-4" />
                Thử lại
              </Button>
            )}
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="rounded-full"
              onClick={onChooseFile}
            >
              Chọn file khác
            </Button>
          </div>
        </Alert>
      )}

      {slidesError && (
        <Alert variant="destructive" className="mt-3" title="Không tải được danh sách trang">
          Kiểm tra kết nối rồi thử lại; nếu vừa tải PDF xong, hãy tải lại trang.
        </Alert>
      )}

      {pendingSlides.length > 0 && (
        <Alert
          variant="info"
          className="mt-3"
          title={`${pendingSlides.length} trang đang được index cho trợ lý học tập`}
        >
          Hệ thống đang xử lý nền; bạn có thể tiếp tục soạn nội dung. Khóa học chỉ
          xuất bản được khi tất cả trang đã index xong.
        </Alert>
      )}

      {unindexedSlides.length > 0 && (
        <Alert
          variant="destructive"
          className="mt-3"
          title={`${unindexedSlides.length} trang chưa index được cho trợ lý học tập`}
        >
          <p>
            Trợ lý sẽ không tìm thấy nội dung các trang này. Lỗi:{" "}
            {unindexedSlides[0].embeddingError || "chưa có thông tin"}. Khóa học
            sẽ không xuất bản được cho tới khi tất cả trang index xong.
          </p>
          {reindexError && <p className="mt-1 text-xs">{reindexError}</p>}
          <div className="mt-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="rounded-full border-border bg-card"
              onClick={onRetryIndex}
              disabled={reindexing}
            >
              <Icon
                name={reindexing ? "ri-loader-4-line" : "ri-refresh-line"}
                className={cn("size-4", reindexing && "animate-spin")}
              />
              {reindexing ? "Đang xử lý…" : "Thử lại index"}
            </Button>
          </div>
        </Alert>
      )}
    </>
  );
}
