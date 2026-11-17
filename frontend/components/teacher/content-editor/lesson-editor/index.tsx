"use client";

import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useRuntimeConfig } from "@/hooks/use-runtime-config";
import { useLessonSlidesAdmin } from "@/hooks/use-teacher";
import { reindexLessonSlides, uploadLessonSlides } from "@/lib/api/teacher";
import type { LessonNode } from "@/lib/types/domain";
import {
  ALLOWED_SLIDE_EXTENSIONS,
  slideLimitsHint,
  validateSlideFile,
} from "../editor-helpers";
import { SlideCheckSection } from "./slide-check-section";
import { UploadSection } from "./upload-section";
import { waitForImportJob, type UploadState } from "./upload-helpers";
import { queryKeys } from "@/lib/query-keys";

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
  const { maxUploadBytes, maxSlidePages } = useRuntimeConfig();
  const limits = { maxUploadBytes, maxSlidePages };
  const limitsHint = slideLimitsHint(limits);
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
  const [reindexing, setReindexing] = useState(false);
  const [reindexError, setReindexError] = useState("");

  const uploading = upload.status === "uploading";
  const slideCount = Math.max(lesson.slides, slides.length);
  const hasSlides = slideCount > 0;
  const unindexedSlides = slides.filter(
    (slide) =>
      slide.embeddingStatus === "failed" || slide.embeddingStatus === "none",
  );
  const pendingSlides = slides.filter((slide) => slide.embeddingStatus === "pending");

  const retryIndex = async () => {
    setReindexing(true);
    setReindexError("");
    try {
      await reindexLessonSlides(lesson.id);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.teacher.lessonSlides(lesson.id) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.teacher.courseTree(courseId) }),
      ]);
    } catch (error) {
      setReindexError(
        error instanceof Error ? error.message : "Không bắt đầu index lại được.",
      );
    } finally {
      setReindexing(false);
    }
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
        queryClient.invalidateQueries({ queryKey: queryKeys.teacher.lessonSlides(lesson.id) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.teacher.courseTree(courseId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.teacher.coursesRoot }),
      ]);
      // Worker index nền ngay sau khi job import xong; làm mới thêm một lần
      // để bắt trạng thái pending và bắt đầu poll.
      window.setTimeout(() => {
        void queryClient.invalidateQueries({
          queryKey: queryKeys.teacher.lessonSlides(lesson.id),
        });
      }, 3000);
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
    const problem = validateSlideFile(file, limits);
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

  const retryLastFile = () => {
    if (!lastFile) return;
    const problem = validateSlideFile(lastFile, limits);
    if (problem) {
      setUpload({ status: "error", fileName: lastFile.name, message: problem });
      return;
    }
    if (hasSlides) setPendingReplace(lastFile);
    else void startUpload(lastFile);
  };

  return (
    <div className="space-y-6">
      <input
        ref={fileRef}
        type="file"
        accept={ALLOWED_SLIDE_EXTENSIONS.join(",")}
        className="sr-only"
        aria-label={`Chọn tài liệu slide cho ${lesson.title}`}
        onChange={(event) => {
          if (event.target.files) chooseFile(event.target.files);
          event.target.value = "";
        }}
      />

      {/* 1) Tài liệu: tải PDF → 2) kiểm tra tài liệu (lưới trang + xem trước). */}
      <UploadSection
        limitsHint={limitsHint}
        canManage={canManage}
        uploading={uploading}
        hasSlides={hasSlides}
        slideCount={slideCount}
        dragOver={dragOver}
        upload={upload}
        lastFile={lastFile}
        slidesError={slidesError}
        pendingSlides={pendingSlides}
        unindexedSlides={unindexedSlides}
        reindexing={reindexing}
        reindexError={reindexError}
        onOpenFileDialog={openFileDialog}
        onDragOver={() => setDragOver(true)}
        onDragLeave={() => setDragOver(false)}
        onDrop={(files) => chooseFile(files)}
        onRetry={retryLastFile}
        onChooseFile={openFileDialog}
        onRetryIndex={() => void retryIndex()}
      />

      <SlideCheckSection slides={slides} />

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
