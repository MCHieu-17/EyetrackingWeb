import { fetchSlideImportJob, type SlideImportJob } from "@/lib/api/teacher";

/** Trạng thái tài liệu: idle → uploading → success | error (giữ file để thử lại). */
export type UploadState =
  | { status: "idle" }
  | { status: "uploading"; fileName: string }
  | { status: "success"; fileName: string; pages: number }
  | { status: "error"; fileName: string; message: string };

/** Poll job import slide cho tới khi xong/thất bại/hủy hoặc quá 10 phút. */
export async function waitForImportJob(
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
