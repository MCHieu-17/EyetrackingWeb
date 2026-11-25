"use client";

import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Input, Textarea } from "@/components/ui/input";
import { useUnsavedGuard } from "@/components/teacher/unsaved-guard";
import { createCourse } from "@/lib/api/teacher";
import { queryKeys } from "@/lib/query-keys";

/**
 * Bước đầu tiên của luồng soạn khóa học: chỉ tạo bản nháp.
 *
 * Chương, bài giảng PDF, bài tập trắc nghiệm và học viên được thêm ngay trong
 * workspace sau khi tạo — nhờ vậy giáo viên không phải hoàn tất PDF/khóa học
 * trước mới được soạn bài tập.
 */
export function NewCourseSetup({
  onCreated,
  onCancel,
}: {
  onCreated: (id: string) => void;
  onCancel: () => void;
}) {
  const queryClient = useQueryClient();
  const guard = useUnsavedGuard();

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isDirty = useMemo(
    () => Boolean(title.trim() || description.trim()),
    [title, description],
  );

  useEffect(() => {
    if (!guard) return;
    return guard.register({ label: "khóa học mới", isDirty: () => isDirty });
  }, [guard, isDirty]);

  const create = async () => {
    const cleanTitle = title.trim();
    if (!cleanTitle) {
      setError("Cần nhập tên khóa học trước khi tạo.");
      return;
    }

    setCreating(true);
    setError(null);
    try {
      const created = await createCourse({
        title: cleanTitle,
        description: description.trim() || undefined,
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.teacher.coursesRoot });
      onCreated(created.id);
    } catch (e) {
      setError(
        `Không tạo được khóa học: ${e instanceof Error ? e.message : "lỗi không xác định"}`,
      );
      setCreating(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <div className="border-b border-border pb-6">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
          Khóa học mới
        </p>
        <h2 className="mt-3 font-display text-3xl font-semibold tracking-[-0.04em] text-foreground sm:text-4xl">
          Tạo khóa học
        </h2>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">
          Đặt tên và mô tả trước. Sau khi tạo, bạn có thể thêm chương, bài giảng PDF và bài tập
          trắc nghiệm trong cùng một màn hình — không cần hoàn tất khóa học trước.
        </p>
      </div>

      <section className="space-y-5 rounded-2xl border border-border bg-card p-5 shadow-xs sm:p-7">
        <div className="space-y-1.5">
          <label htmlFor="new-course-title" className="block text-sm font-medium text-foreground">
            Tên khóa học <span className="text-destructive">*</span>
          </label>
          <Input
            id="new-course-title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Ví dụ: Lập trình Python cơ bản"
            className="h-11 rounded-xl"
            autoFocus
            disabled={creating}
          />
        </div>

        <div className="space-y-1.5">
          <label htmlFor="new-course-description" className="block text-sm font-medium text-foreground">
            Mô tả
          </label>
          <Textarea
            id="new-course-description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            rows={4}
            placeholder="Tóm tắt nội dung, mục tiêu khóa học…"
            disabled={creating}
          />
        </div>

        {error && <Alert variant="destructive" title={error} />}

        <div className="flex flex-col-reverse gap-2 border-t border-border/60 pt-4 sm:flex-row sm:justify-end">
          <Button
            type="button"
            variant="outline"
            className="rounded-full border-border bg-card"
            onClick={onCancel}
            disabled={creating}
          >
            Hủy
          </Button>
          <Button
            type="button"
            className="rounded-full bg-primary px-6 text-primary-foreground hover:bg-primary-hover"
            onClick={() => void create()}
            disabled={creating || !title.trim()}
          >
            <Icon name={creating ? "ri-loader-4-line" : "ri-add-line"} className={creating ? "size-4 animate-spin" : "size-4"} />
            {creating ? "Đang tạo…" : "Tạo khóa học"}
          </Button>
        </div>
      </section>
    </div>
  );
}
