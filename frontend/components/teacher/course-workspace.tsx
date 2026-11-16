"use client";

import { Suspense } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Icon } from "@/components/ui/icon";
import { FullPageSpinner } from "@/components/ui/spinner";
import { LazyAoiEditor } from "@/components/teacher/aoi/lazy-aoi-editor";
import { NewCourseSetup } from "@/components/teacher/content-editor/new-course-setup";
import { UnsavedGuardProvider, useUnsavedGuard } from "@/components/teacher/unsaved-guard";
import { useTeacherCourses } from "@/hooks/use-teacher";
import { STATUS_LABEL } from "@/lib/constants";
import { cn } from "@/lib/utils";

type View = "content" | "info" | "students" | "aoi" | "visualization";

function TabLoading({ label }: { label: string }) {
  return (
    <div className="flex min-h-[320px] items-center justify-center">
      <FullPageSpinner label={label} />
    </div>
  );
}

// Tab nội dung chỉ tải khi thực sự được mở — giảm JS ban đầu của workspace.
const ContentEditor = dynamic(
  () => import("@/components/teacher/content-editor").then((mod) => mod.ContentEditor),
  {
    ssr: false,
    loading: () => <TabLoading label="Đang tải nội dung khóa học..." />,
  },
);

const CourseInfoTab = dynamic(
  () => import("@/components/teacher/course-info-tab").then((mod) => mod.CourseInfoTab),
  {
    ssr: false,
    loading: () => <TabLoading label="Đang tải thông tin khóa học..." />,
  },
);

const StudentsTab = dynamic(
  () => import("@/components/teacher/students-tab").then((mod) => mod.StudentsTab),
  {
    ssr: false,
    loading: () => <TabLoading label="Đang tải danh sách học viên..." />,
  },
);

const VisualizationTab = dynamic(
  () =>
    import("@/components/teacher/visualization").then(
      (mod) => mod.VisualizationTab,
    ),
  {
    ssr: false,
    loading: () => <TabLoading label="Đang tải dữ liệu trực quan hoá..." />,
  },
);

const TABS: { key: View; label: string }[] = [
  { key: "content", label: "Nội dung" },
  { key: "info", label: "Thông tin" },
  { key: "students", label: "Học viên" },
  { key: "aoi", label: "Vùng phân tích" },
  { key: "visualization", label: "Trực quan hoá" },
];

function Workspace({ courseId }: { courseId: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const guard = useUnsavedGuard();
  const isNew = courseId === "c-new";
  const tabParam = searchParams.get("tab");
  // Khóa mới không có tab: luôn hiển thị trang tạo khóa học một-bước.
  // "settings" là đường dẫn cũ sau khi gộp tab — chuyển về tab Thông tin.
  const view: View = isNew
    ? "content"
    : tabParam === "settings"
      ? "info"
      : TABS.some((t) => t.key === tabParam)
        ? (tabParam as View)
        : "content";

  const { data: courses = [], isLoading, isError, refetch } = useTeacherCourses();
  const course = courses.find((c) => c.id === courseId);
  const canManage = isNew || course?.isOwner === true;
  const title = isNew ? "Khóa học mới" : course?.title ?? "Khóa học";
  const status = isNew ? "draft" : course?.status ?? "draft";

  /** Điều hướng trong workspace — hỏi trước nếu trình soạn còn thay đổi chưa lưu. */
  const go = (href: string) => {
    const proceed = () => router.push(href);
    if (guard) guard.confirmLeave(proceed);
    else proceed();
  };

  if (!isNew && isLoading) return <FullPageSpinner label="Đang tải khóa học..." />;
  if (!isNew && isError) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16">
        <ErrorState
          title="Không tải được khóa học"
          description="Vui lòng kiểm tra kết nối và thử lại."
          onRetry={() => void refetch()}
        />
      </div>
    );
  }

  return (
    <div className="min-h-dvh bg-[#f5f6f2] text-black">
      <header className="sticky top-0 z-30 border-b border-[#eeeee9] bg-[#f5f6f2]/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1440px] flex-wrap items-center gap-3 px-4 py-3 sm:px-8 lg:px-12">
          <Button
            asChild
            variant="ghost"
            size="icon"
            aria-label="Quay lại danh sách khóa học"
            title="Về danh sách khóa học"
            className="rounded-full hover:bg-white"
          >
            <Link
              href="/teacher"
              onClick={(event) => {
                event.preventDefault();
                go("/teacher");
              }}
            >
              <Icon name="ri-arrow-left-line" className="size-5" />
            </Link>
          </Button>

          <div className="min-w-0 flex-1 border-l border-black/10 pl-4">
            <p className="truncate text-sm font-semibold tracking-[-0.01em] text-black">{title}</p>
            <div className="mt-1 flex items-center gap-2 text-[11px] text-black/60">
              <span className="rounded-full bg-[#e8f1e6] px-2 py-0.5 font-medium text-[#52704f]">
                {STATUS_LABEL[status]}
              </span>
              {!isNew && course && <span className="truncate">{course.students} học viên</span>}
            </div>
          </div>

          {!isNew && (
            <nav
              aria-label="Khu vực quản lý"
              className="order-last -mx-1 flex w-full items-center gap-1 overflow-x-auto rounded-full border border-[#eeeee9] bg-white p-1 shadow-xs sm:order-none sm:mx-0 sm:w-auto"
            >
              {TABS.map((item) => {
                const active = view === item.key;
                const href = `/teacher/courses/${courseId}?tab=${item.key}`;
                return (
                  <Link
                    key={item.key}
                    href={href}
                    aria-current={active ? "page" : undefined}
                    onClick={(event) => {
                      if (active) {
                        event.preventDefault();
                        return;
                      }
                      event.preventDefault();
                      go(href);
                    }}
                    className={cn(
                      "flex h-8 shrink-0 items-center justify-center whitespace-nowrap rounded-full px-3.5 text-xs font-semibold transition-colors",
                      active ? "bg-black text-white shadow-sm" : "text-black/60 hover:text-black",
                    )}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          )}
        </div>
      </header>

      <main className="mx-auto min-h-[calc(100dvh-73px)] w-full max-w-[1440px] rounded-t-[28px] border border-b-0 border-[#eeeee9] bg-[#fdfdfa] px-4 py-8 shadow-[0_-1px_12px_rgba(30,35,25,0.025)] sm:px-8 lg:px-12 lg:py-12">
        {isNew ? (
          <NewCourseSetup
            onCreated={(id) => router.replace(`/teacher/courses/${id}?tab=content`)}
            onCancel={() => go("/teacher")}
          />
        ) : view === "content" ? (
          <ContentEditor
            courseId={courseId}
            canManage={canManage}
            courseTitle={title}
            courseStatus={status}
          />
        ) : null}
        {!isNew && view === "info" && <CourseInfoTab courseId={courseId} canManage={canManage} />}
        {!isNew && view === "students" && <StudentsTab courseId={courseId} canManage={canManage} />}
        {!isNew && view === "visualization" && (
          <VisualizationTab courseId={courseId} />
        )}
        {!isNew && view === "aoi" && (
          <div className="-mx-4 -my-8 sm:-mx-8 lg:-mx-12 lg:-my-12">
            <LazyAoiEditor
              courseId={courseId}
              courseTitle={title}
              canManage={canManage}
            />
          </div>
        )}
      </main>
    </div>
  );
}

export function CourseWorkspace({ courseId }: { courseId: string }) {
  return (
    <Suspense fallback={<FullPageSpinner label="Đang tải khóa học..." />}>
      <UnsavedGuardProvider>
        <Workspace courseId={courseId} />
      </UnsavedGuardProvider>
    </Suspense>
  );
}
