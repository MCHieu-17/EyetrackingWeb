"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useLessonSlidesAdmin } from "@/hooks/use-teacher";
import { MAX_SLIDE_PAGES, MAX_UPLOAD_BYTES, MAX_UPLOAD_LABEL } from "@/lib/api/client";
import {
  fetchSlideImportJob,
  uploadLessonSlides,
  type SlideImportJob,
} from "@/lib/api/teacher";
import { cn } from "@/lib/utils";
import type { LessonNode } from "@/lib/types/domain";
import { KeySlideControls } from "./key-slide-controls";
import { SlidePreview } from "./slide-preview";

/** Trạng thái tài liệu: idle → uploading → success | error (giữ file để thử lại). */
type UploadState =
  | { status: "idle" }
  | { status: "uploading"; fileName: string }
  | { status: "success"; fileName: string; pages: number }
  | { status: "error"; fileName: string; message: string };

const ALLOWED_EXTENSIONS = [".pdf", ".pptx", ".ppt", ".odp"];
const LIMITS_HINT = `PDF, PPTX, PPT, ODP · tối đa ${MAX_UPLOAD_LABEL} · tối đa ${MAX_SLIDE_PAGES} trang — mỗi trang thành 1 slide.`;

async function waitForImportJob(
  lessonId: string,
  jobId: string,
): Promise<SlideImportJob> {
  const deadline = Date.now() + 10 * 60 * 1000;
  while (Date.now() < deadline) {
    const job = await fetchSlideImportJob(lessonId, jobId);
    if (
      job.status === "ready" ||
      job.status === "failed" ||
      job.status === "cancelled"
    ) {
      return job;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 2000));
  }
  throw new Error("Quá thời gian chờ xử lý tài liệu. Hãy thử lại.");
}

export function LessonEditor({
  lesson,
  courseId,
  canManage,
}: {
  lesson: LessonNode;
  courseId: string;
  canManage: boolean;
}) {
  const queryClient = useQueryClient();
  const {
    data: slides = [],
    isLoading: slidesLoading,
    isError: slidesError,
  } = useLessonSlidesAdmin(lesson.id);

  const fileRef = useRef<HTMLInputElement>(null);
  const [upload, setUpload] = useState<UploadState>({ status: "idle" });
  const [lastFile, setLastFile] = useState<File | null>(null);
  const [pendingReplace, setPendingReplace] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const uploading = upload.status === "uploading";
  const slideCount = Math.max(lesson.slides, slides.length);
  const hasSlides = slideCount > 0;
  const failedSlides = slides.filter((slide) => slide.embeddingStatus === "failed");

  const validate = (file: File): string | null => {
    const lower = file.name.toLowerCase();
    const extension = lower.slice(lower.lastIndexOf("."));
    if (!ALLOWED_EXTENSIONS.includes(extension)) {
      return `"${file.name}" không phải tài liệu slide hợp lệ. Hãy chọn PDF, PPTX, PPT hoặc ODP.`;
    }
    if (file.size > MAX_UPLOAD_BYTES)
      return `File "${file.name}" vượt quá ${MAX_UPLOAD_LABEL} cho phép.`;
    return null;
  };

  const startUpload = async (file: File) => {
    setLastFile(file);
    setUpload({ status: "uploading", fileName: file.name });
    try {
      const result = await uploadLessonSlides(lesson.id, file);
      const job = await waitForImportJob(lesson.id, result.jobId);
      if (job.status !== "ready") {
        throw new Error(
          job.error ||
            (job.status === "cancelled"
              ? "Lần tải lên này đã bị thay thế bởi lần tải mới hơn."
              : "Không tạo được slide từ tài liệu."),
        );
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["teacher", "lesson-slides", lesson.id] }),
        queryClient.invalidateQueries({ queryKey: ["teacher", "course-tree", courseId] }),
        queryClient.invalidateQueries({ queryKey: ["teacher", "courses"] }),
      ]);
      setUpload({
        status: "success",
        fileName: file.name,
        pages: job.pageCount ?? 0,
      });
    } catch (error) {
      setUpload({
        status: "error",
        fileName: file.name,
        message:
          error instanceof Error
            ? error.message
            : "Không tải được tài liệu lên hệ thống.",
      });
    }
  };

  const chooseFile = (files: FileList | File[] | null) => {
    const file = files ? Array.from(files)[0] : null;
    if (!file) return;
    const problem = validate(file);
    if (problem) {
      setLastFile(file);
      setUpload({ status: "error", fileName: file.name, message: problem });
      return;
    }
    // Bài đã có slide: thay PDF sẽ xoá toàn bộ slide cũ → xác nhận trước.
    if (hasSlides) {
      setPendingReplace(file);
      return;
    }
    setLastFile(file);
    setUpload({ status: "idle" });
    void startUpload(file);
  };

  const openFileDialog = () => fileRef.current?.click();

  return (
    <div className="space-y-6">
      <input
        ref={fileRef}
        type="file"
        accept=".pdf,.pptx,.ppt,.odp"
        className="sr-only"
        aria-label={`Chọn tài liệu slide cho ${lesson.title}`}
        onChange={(event) => {
          if (event.target.files) chooseFile(event.target.files);
          event.target.value = "";
        }}
      />

      {/* 1) Tài liệu: tải PDF → 2) kiểm tra tài liệu (lưới trang + xem trước). */}
      <section className="rounded-[20px] border border-[#eeeee9] bg-white p-4 shadow-xs sm:p-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <h3 className="text-base font-semibold text-black">Tài liệu bài giảng</h3>
            <p className="mt-1 text-sm leading-6 text-black/65">
              {hasSlides
                ? `Đang dùng ${slideCount} trang slide. Tải tài liệu mới để tạo lại toàn bộ.`
                : "Tải PDF/PPTX/PPT/ODP lên để tạo slide cho bài giảng này."}
            </p>
            <p className="mt-1 text-xs leading-5 text-black/55">{LIMITS_HINT}</p>
          </div>
          {canManage && (
            <Button
              type="button"
              variant="outline"
              className="shrink-0 rounded-full border-black/10 bg-white"
              onClick={openFileDialog}
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
            onClick={openFileDialog}
            onDragOver={(event) => {
              event.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragOver(false);
              chooseFile(event.dataTransfer.files);
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
                <span className="text-xs text-black/55">{LIMITS_HINT}</span>
              </>
            )}
          </button>
        )}

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
            <p className="mt-1 text-xs text-black/60">
              File “{upload.fileName}” vẫn được giữ — bạn có thể thử lại hoặc chọn file khác.
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {lastFile && (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="rounded-full border-black/10 bg-white"
                  onClick={() => {
                    const problem = validate(lastFile);
                    if (problem) {
                      setUpload({ status: "error", fileName: lastFile.name, message: problem });
                      return;
                    }
                    if (hasSlides) setPendingReplace(lastFile);
                    else void startUpload(lastFile);
                  }}
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
                onClick={openFileDialog}
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

        {failedSlides.length > 0 && (
          <Alert
            variant="destructive"
            className="mt-3"
            title={`${failedSlides.length} trang chưa index được cho trợ lý học tập`}
          >
            Trợ lý sẽ không tìm thấy nội dung các trang này. Lỗi:{" "}
            {failedSlides[0].embeddingError || "không rõ"}. Hệ thống tự thử lại khi bạn tải lại
            PDF; quản trị viên có thể chạy reindex nếu lỗi kéo dài.
          </Alert>
        )}
      </section>

      {/* Kiểm tra tài liệu */}
      {slides.length > 0 && (
        <section className="rounded-[20px] border border-[#eeeee9] bg-white p-4 shadow-xs sm:p-6">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-base font-semibold text-black">Kiểm tra tài liệu</h3>
            <span className="text-xs font-medium text-black/60">
              {slides.length} trang · bấm một trang để xem trước
            </span>
          </div>
          <SlidePreview slides={slides} />
        </section>
      )}

      {/* Ít dùng → gập lại, không lồng thêm accordion nào khác. */}
      {slides.length > 0 && (
        <details className="rounded-[20px] border border-[#eeeee9] bg-white p-4 shadow-xs sm:p-5">
          <summary className="cursor-pointer text-sm font-semibold text-black">
            Cài đặt nâng cao (trang trọng tâm)
          </summary>
          <p className="mt-2 text-xs leading-5 text-black/60">
            Đánh dấu trang trọng tâm để tính điểm hoàn thành bài học. Những thiết lập này ảnh
            hưởng tới cách tính mức độ hoàn thành của học viên.
          </p>
          <p className="mt-1 text-xs leading-5 text-black/60">
            Chấm điểm nhìn là thiết lập cấp khóa học —{" "}
            <Link
              href={`/teacher/courses/${courseId}?tab=info`}
              className="font-medium text-[#3f573c] underline underline-offset-4"
            >
              mở tab Thông tin
            </Link>
            .
          </p>
          <div className="mt-1">
            <KeySlideControls
              lessonId={lesson.id}
              canDelete={canManage}
              slides={slides}
            />
          </div>
        </details>
      )}

      {slidesLoading && slides.length === 0 && (
        <p className="text-sm text-black/55">Đang tải tài liệu bài giảng…</p>
      )}

      <ConfirmDialog
        open={pendingReplace !== null}
        onOpenChange={(open) => !open && setPendingReplace(null)}
        title="Thay tài liệu của bài giảng?"
        description={
          `Tải "${pendingReplace?.name ?? ""}" sẽ XÓA toàn bộ ${slideCount} trang slide hiện có và ` +
          "tạo lại slide từ file mới. Nếu bài học đã có dữ liệu điểm nhìn của " +
          "học viên, hệ thống sẽ từ chối thay để không phá dữ liệu phân tích."
        }
        confirmLabel="Thay tài liệu"
        destructive
        onConfirm={() => {
          const file = pendingReplace;
          setPendingReplace(null);
          if (file) void startUpload(file);
        }}
      />
    </div>
  );
}
