"use client";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import type { ModuleNode } from "@/lib/types/domain";

/**
 * Kiểm tra nội dung trước khi xuất bản.
 *
 * Quy tắc CHẶN (`blocking`) khớp `content.validate_draft` ở backend: cần tên
 * khóa học, có chương, có ít nhất một mục, bài giảng phải có slide và toàn bộ
 * slide phải index xong, bài tập phải có câu hỏi. Bài tập còn nháp chỉ là cảnh
 * báo vì xuất bản khóa học sẽ đưa nó vào bản published.
 */
export interface PublishIssue {
  key: string;
  /** Tên chương · bài liên quan. */
  item: string;
  /** Mô tả vấn đề cần sửa. */
  label: string;
  blocking: boolean;
  lessonId?: string;
}

export interface PublishReport {
  blocking: boolean;
  issues: PublishIssue[];
}

export function publishReport(title: string, tree: ModuleNode[]): PublishReport {
  const issues: PublishIssue[] = [];
  const items = tree.flatMap((module) => module.lessons);

  if (!title.trim()) {
    issues.push({ key: "title", item: "Khóa học", label: "Chưa có tên khóa học", blocking: true });
  }
  if (tree.length === 0) {
    issues.push({ key: "modules", item: "Khóa học", label: "Chưa có chương nào", blocking: true });
  } else if (items.length === 0) {
    issues.push({
      key: "items",
      item: "Khóa học",
      label: "Chưa có bài giảng hay bài tập nào",
      blocking: true,
    });
  }

  for (const mod of tree) {
    for (const lesson of mod.lessons) {
      const item = `${mod.title} · ${lesson.title}`;
      if (lesson.kind === "lesson" && lesson.slides === 0) {
        issues.push({
          key: `slides-${lesson.id}`,
          item,
          label: "Bài giảng chưa có tài liệu PDF — không thể xuất bản",
          blocking: true,
          lessonId: lesson.id,
        });
      }
      if (lesson.kind === "lesson" && lesson.slides > 0) {
        const ready = lesson.slidesReady ?? 0;
        const failed = lesson.slidesFailed ?? 0;
        const pending = lesson.slidesPending ?? 0;
        if (ready < lesson.slides) {
          const details = [
            failed > 0 ? `${failed} lỗi` : null,
            pending > 0 ? `${pending} đang xử lý` : null,
          ].filter(Boolean);
          issues.push({
            key: `index-${lesson.id}`,
            item,
            label:
              `Còn ${lesson.slides - ready} trang chưa index xong cho trợ lý học tập` +
              (details.length ? ` (${details.join(", ")})` : "") +
              " — khóa học chỉ xuất bản được khi tất cả trang đã index",
            blocking: true,
            lessonId: lesson.id,
          });
        }
      }
      if (lesson.kind === "quiz" && (lesson.questionCount ?? 0) === 0) {
        issues.push({
          key: `questions-${lesson.id}`,
          item,
          label: "Bài tập chưa có câu hỏi nào — không thể xuất bản",
          blocking: true,
          lessonId: lesson.id,
        });
      }
      if (lesson.kind === "quiz" && lesson.quizStatus === "draft" && (lesson.questionCount ?? 0) > 0) {
        issues.push({
          key: `draft-${lesson.id}`,
          item,
          label: "Bài tập còn ở bản nháp — sinh viên chưa thấy để làm",
          blocking: false,
          lessonId: lesson.id,
        });
      }
    }
  }

  return { blocking: issues.some((issue) => issue.blocking), issues };
}

export function PublishIssueList({
  issues,
  onOpenItem,
}: {
  issues: PublishIssue[];
  onOpenItem?: (lessonId: string) => void;
}) {
  if (issues.length === 0) return null;
  return (
    <ul className="space-y-2">
      {issues.map((issue) => (
        <li
          key={issue.key}
          className={cn(
            "flex flex-col gap-2 rounded-xl border p-3 sm:flex-row sm:items-center sm:justify-between",
            issue.blocking
              ? "border-destructive/25 bg-destructive/5"
              : "border-warning/30 bg-warning/8",
          )}
        >
          <div className="min-w-0">
            <p className="text-sm font-medium text-foreground">{issue.item}</p>
            <p className="mt-0.5 flex items-center gap-1.5 text-xs leading-5 text-muted-foreground">
              <Icon
                name={issue.blocking ? "ri-error-warning-line" : "ri-information-line"}
                className={cn("size-3.5 shrink-0", issue.blocking ? "text-destructive" : "text-warning")}
              />
              {issue.label}
              {!issue.blocking && <span className="text-muted-foreground">· chỉ là cảnh báo</span>}
            </p>
          </div>
          {issue.lessonId && onOpenItem && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="shrink-0 self-start rounded-full border-border bg-card sm:self-auto"
              onClick={() => onOpenItem(issue.lessonId as string)}
            >
              Mở mục này
            </Button>
          )}
        </li>
      ))}
    </ul>
  );
}

export function PublishChecklistDialog({
  open,
  onOpenChange,
  report,
  onOpenItem,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  report: PublishReport;
  onOpenItem?: (lessonId: string) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Kiểm tra trước khi xuất bản</DialogTitle>
          <DialogDescription>
            {report.issues.length === 0
              ? "Nội dung đã sẵn sàng để xuất bản."
              : report.blocking
                ? "Còn mục bắt buộc phải sửa trước khi xuất bản."
                : "Không có mục bắt buộc nào thiếu — các cảnh báo dưới đây chỉ để bạn cân nhắc."}
          </DialogDescription>
        </DialogHeader>
        <div className="max-h-[55vh] overflow-y-auto px-6 pb-2">
          {report.issues.length === 0 ? (
            <p className="flex items-center gap-2 rounded-xl border border-success/25 bg-success/8 p-3 text-sm text-foreground">
              <Icon name="ri-checkbox-circle-fill" className="size-4 text-success" />
              Tên khóa học, chương và các mục đã đầy đủ.
            </p>
          ) : (
            <PublishIssueList issues={report.issues} onOpenItem={onOpenItem} />
          )}
        </div>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            className="rounded-full"
            onClick={() => onOpenChange(false)}
          >
            Đóng
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
