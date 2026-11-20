"use client";

import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { useCourseVisits, useAoiSummary } from "@/hooks/use-visualization";
import { rebuildAoiHits } from "@/lib/api/aoi";
import { queryKeys } from "@/lib/query-keys";
import type { ModuleNode } from "@/lib/types/domain";
import type {
  AoiSummaryQuery,
  SummaryScope,
  SummarySurface,
} from "@/lib/types/visualization";
import { AoiBarChart } from "./aoi-bar-chart";
import { AoiCompositionChart } from "./aoi-composition-chart";
import { AoiTable } from "./aoi-table";
import { HeatmapCard } from "./heatmap-card";
import { StudentCompareChart } from "./student-compare-chart";
import { csvForSummary, visibleAois } from "./summary-helpers";
import { SummaryCards } from "./summary-cards";
import { SummaryFilters } from "./summary-filters";
import { VisitTrendChart } from "./visit-trend-chart";

function localDateIso(value: string, endOfDay = false): string | undefined {
  if (!value) return undefined;
  const date = new Date(`${value}T${endOfDay ? "23:59:59.999" : "00:00:00.000"}`);
  return Number.isNaN(date.getTime()) ? undefined : date.toISOString();
}

interface SummaryQueryInput {
  scope: SummaryScope;
  lessonId: string;
  from: string;
  to: string;
  surface: SummarySurface;
  includeDropped: boolean;
  onlyCounted: boolean;
  resolvedStudentId: string;
  resolvedVisitId: string;
  selectedStudentIds: string[];
}

/**
 * Mặc định tính cả lượt ngắn (`includeShort: true`). Chỉ khi người dùng bật
 * "Chỉ tính lượt >= ngưỡng" mới gửi `includeShort: false`.
 */
function buildSummaryQuery(input: SummaryQueryInput): AoiSummaryQuery {
  const common = {
    lessonIds: input.lessonId ? [input.lessonId] : [],
    from: localDateIso(input.from),
    to: localDateIso(input.to, true),
    surface: input.surface,
    includeDropped: input.includeDropped,
    includeShort: !input.onlyCounted,
  };
  if (input.scope === "visit") {
    return {
      ...common,
      visitIds: input.resolvedVisitId ? [input.resolvedVisitId] : [],
    };
  }
  if (input.scope === "student") {
    return {
      ...common,
      studentIds: input.resolvedStudentId ? [input.resolvedStudentId] : [],
    };
  }
  return { ...common, studentIds: input.selectedStudentIds };
}

function HeatmapSection({
  courseId,
  query,
  lessons,
}: {
  courseId: string;
  query: AoiSummaryQuery;
  lessons: { id: string; title: string }[];
}) {
  return (
    <section className="rounded-[20px] border border-[#eeeee9] bg-white p-4 shadow-xs xl:col-span-2">
      <div className="mb-3 flex items-center gap-2">
        <Icon name="ri-fire-line" className="size-4 text-[#36533a]" />
        <h3 className="text-sm font-semibold text-black">
          Bản đồ nhiệt theo slide
        </h3>
        <span className="ml-auto text-[11px] text-black/40">
          {lessons.length} bài giảng có slide
        </span>
      </div>
      <HeatmapCard courseId={courseId} baseQuery={query} lessons={lessons} />
    </section>
  );
}

export function SummaryPanel({
  courseId,
  tree,
  initialStudentId,
  initialScope = "cohort",
}: {
  courseId: string;
  tree: ModuleNode[];
  initialStudentId?: string | null;
  initialScope?: SummaryScope;
}) {
  const visitsQuery = useCourseVisits(courseId, { limit: 1000 });
  const visits = useMemo(() => visitsQuery.data ?? [], [visitsQuery.data]);
  const queryClient = useQueryClient();

  const [scope, setScope] = useState<SummaryScope>(
    initialStudentId ? "student" : initialScope,
  );
  const [studentId, setStudentId] = useState(initialStudentId ?? "");
  const [selectedStudentIds, setSelectedStudentIds] = useState<string[]>([]);
  const [visitId, setVisitId] = useState("");
  const [lessonId, setLessonId] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [surface, setSurface] = useState<SummarySurface>("all");
  const [includeDropped, setIncludeDropped] = useState(false);
  const [onlyCounted, setOnlyCounted] = useState(false);
  const [rebuilding, setRebuilding] = useState(false);
  const [rebuildNote, setRebuildNote] = useState<string | null>(null);

  const students = useMemo(() => {
    const map = new Map<string, { id: string; name: string }>();
    for (const visit of visits) {
      if (!map.has(visit.studentId)) {
        map.set(visit.studentId, {
          id: visit.studentId,
          name: visit.studentName,
        });
      }
    }
    return [...map.values()].sort((a, b) => a.name.localeCompare(b.name, "vi"));
  }, [visits]);

  const resolvedStudentId = students.some((student) => student.id === studentId)
    ? studentId
    : students[0]?.id ?? "";
  const studentVisits = visits.filter(
    (visit) => visit.studentId === resolvedStudentId,
  );
  const resolvedVisitId = studentVisits.some((visit) => visit.id === visitId)
    ? visitId
    : studentVisits[0]?.id ?? "";

  const lessons = useMemo(
    () => tree.flatMap((module) => module.lessons),
    [tree],
  );
  const slideLessons = useMemo(
    () => lessons.filter((lesson) => lesson.kind === "lesson" && lesson.slides > 0),
    [lessons],
  );
  const heatmapLessons = useMemo(
    () => slideLessons.map((lesson) => ({ id: lesson.id, title: lesson.title })),
    [slideLessons],
  );

  const query = useMemo<AoiSummaryQuery>(
    () =>
      buildSummaryQuery({
        scope,
        lessonId,
        from,
        to,
        surface,
        includeDropped,
        onlyCounted,
        resolvedStudentId,
        resolvedVisitId,
        selectedStudentIds,
      }),
    [
      from,
      includeDropped,
      lessonId,
      onlyCounted,
      resolvedStudentId,
      resolvedVisitId,
      scope,
      selectedStudentIds,
      surface,
      to,
    ],
  );

  const enabled =
    visits.length > 0 &&
    (scope !== "visit" || Boolean(resolvedVisitId)) &&
    (scope !== "student" || Boolean(resolvedStudentId));
  const summary = useAoiSummary(courseId, query, enabled);

  const resetFilters = () => {
    setStudentId("");
    setSelectedStudentIds([]);
    setVisitId("");
    setLessonId("");
    setFrom("");
    setTo("");
    setSurface("all");
    setIncludeDropped(false);
    setOnlyCounted(false);
  };

  const rebuild = async () => {
    setRebuilding(true);
    setRebuildNote(null);
    try {
      await rebuildAoiHits({ courseId });
      setRebuildNote(
        "Đã xếp hàng phân tích lại. Số liệu sẽ cập nhật sau khi worker xử lý xong.",
      );
      window.setTimeout(() => {
        void summary.refetch();
        void visitsQuery.refetch();
        // Heatmap có query riêng (slideId); invalidate prefix để card tự tải
        // lại sau khi worker phân tích xong.
        void queryClient.invalidateQueries({
          queryKey: queryKeys.visualization.aoiHeatmapRoot(courseId),
        });
      }, 4000);
    } catch {
      setRebuildNote("Không gửi được yêu cầu phân tích lại.");
    } finally {
      setRebuilding(false);
    }
  };

  const downloadCsv = () => {
    if (!summary.data) return;
    const blob = new Blob([`\uFEFF${csvForSummary(summary.data)}`], {
      type: "text/csv;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `aoi-summary-${courseId}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  if (visitsQuery.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-20 rounded-[20px]" />
        <Skeleton className="h-28 rounded-[18px]" />
        <Skeleton className="h-[320px] rounded-[20px]" />
      </div>
    );
  }

  if (visitsQuery.isError) {
    return (
      <ErrorState
        title="Không tải được dữ liệu khóa học"
        description="Vui lòng kiểm tra kết nối và thử lại."
        onRetry={() => void visitsQuery.refetch()}
      />
    );
  }

  if (visits.length === 0) {
    return (
      <EmptyState
        icon="ri-bar-chart-line"
        title="Chưa có dữ liệu để tổng hợp"
        description="Dữ liệu gaze sẽ xuất hiện sau khi học viên học bài và phiên được phân tích."
      />
    );
  }

  const data = summary.data;
  const unlabeledShare = data
    ? data.totals.unlabeledDurationMs / Math.max(1, data.totals.trackedDurationMs)
    : 0;
  const aoiRows = data ? visibleAois(data.byAoi) : [];
  const maxGapMs = data?.meta.maxGapMs ?? 250;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-black/10 pb-5">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-black/35">
            Tổng hợp
          </p>
          <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-black sm:text-3xl">
            Thời lượng nhìn theo vùng
          </h2>
          <p className="mt-1 max-w-2xl text-sm text-black/45">
            Chỉ tính các chuỗi mẫu hợp lệ liên tiếp ≤ {maxGapMs}ms. Số liệu lấy
            từ thống kê AOI đã phân tích của từng lượt xem.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="outline"
            className="rounded-full border-[#eeeee9] bg-white"
            onClick={downloadCsv}
            disabled={!data || aoiRows.length === 0}
          >
            <Icon name="ri-download-line" className="size-4" />
            Xuất CSV
          </Button>
          <Button
            type="button"
            variant="outline"
            className="rounded-full border-[#eeeee9] bg-white"
            onClick={() => void summary.refetch()}
            disabled={summary.isFetching}
          >
            <Icon name="ri-refresh-line" className="size-4" />
            Làm mới
          </Button>
        </div>
      </div>

      <SummaryFilters
        visits={visits}
        lessons={lessons.map((lesson) => ({
          id: lesson.id,
          title: lesson.title,
        }))}
        scope={scope}
        onScope={(next) => {
          setScope(next);
          if (next === "cohort") setSelectedStudentIds([]);
        }}
        studentId={resolvedStudentId}
        onStudent={setStudentId}
        selectedStudentIds={selectedStudentIds}
        onSelectedStudents={setSelectedStudentIds}
        visitId={resolvedVisitId}
        onVisit={setVisitId}
        lessonId={lessonId}
        onLesson={setLessonId}
        from={from}
        onFrom={setFrom}
        to={to}
        onTo={setTo}
        surface={surface}
        onSurface={setSurface}
        includeDropped={includeDropped}
        onIncludeDropped={setIncludeDropped}
        onlyCounted={onlyCounted}
        onOnlyCounted={setOnlyCounted}
        onReset={resetFilters}
      />

      {data &&
        typeof data.meta.shortViewCount === "number" &&
        data.meta.shortViewCount > 0 && (
          <p className="text-xs text-black/45">
            {onlyCounted
              ? `Đã loại ${data.meta.shortViewCount} lượt xem ngắn hơn ngưỡng.`
              : `Đang bao gồm ${data.meta.shortViewCount} lượt xem ngắn hơn ngưỡng. Bật “Chỉ tính lượt >= ngưỡng” để loại các lượt này.`}
          </p>
        )}

      {data && data.meta.staleViewCount > 0 && (
        <div className="flex flex-wrap items-center gap-3 rounded-[18px] border border-[#ecd2c8] bg-[#fdf6f2] px-4 py-3 text-sm text-[#7a3b2b]">
          <Icon name="ri-error-warning-line" className="size-4 shrink-0" />
          <span className="min-w-0 flex-1">
            {data.meta.staleViewCount} lượt xem chưa có thống kê AOI mới. Số
            liệu có thể thiếu cho tới khi phân tích lại.
          </span>
          <Button
            type="button"
            size="xs"
            variant="outline"
            className="rounded-full border-[#e3c6ba] bg-white"
            onClick={() => void rebuild()}
            disabled={rebuilding}
          >
            {rebuilding ? "Đang gửi…" : "Phân tích lại"}
          </Button>
        </div>
      )}
      {rebuildNote && (
        <p className="text-xs text-black/45">{rebuildNote}</p>
      )}

      {unlabeledShare > 0.2 && (
        <div className="flex flex-wrap items-center gap-3 rounded-[18px] border border-[#eadfc6] bg-[#fbf7ec] px-4 py-3 text-sm text-[#7a5b20]">
          <Icon name="ri-error-warning-line" className="size-4 shrink-0" />
          <span className="min-w-0 flex-1">
            {Math.round(unlabeledShare * 100)}% thời gian nhìn rơi ngoài vùng
            AOI. Hãy kiểm tra lại vùng phân tích.
          </span>
          <Button
            asChild
            size="xs"
            variant="outline"
            className="rounded-full border-[#e3d2a8] bg-white"
          >
            <a href={`/teacher/courses/${courseId}?tab=aoi`}>
              <Icon name="ri-edit-line" className="size-3.5" />
              Mở vùng phân tích
            </a>
          </Button>
        </div>
      )}

      {summary.isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-28 rounded-[18px]" />
          <Skeleton className="h-[320px] rounded-[20px]" />
        </div>
      ) : summary.isError || !data ? (
        <ErrorState
          title="Không tải được thống kê AOI"
          description="Vui lòng thử lại hoặc thu hẹp bộ lọc."
          onRetry={() => void summary.refetch()}
        />
      ) : data.totals.contentViewCount === 0 ? (
        <div className="space-y-4">
          <EmptyState
            icon="ri-inbox-line"
            title="Không có dữ liệu trong phạm vi đã chọn"
            description="Thử đổi học viên, ca học, khoảng ngày hoặc bật học viên đã gỡ."
          />
          {/* Heatmap có phạm vi slide riêng; vẫn hiển thị khi bộ lọc tổng hợp
              không có content view (ví dụ surface=quiz). */}
          <HeatmapSection
            courseId={courseId}
            query={query}
            lessons={heatmapLessons}
          />
        </div>
      ) : (
        <>
          <SummaryCards totals={data.totals} />

          <div className="grid gap-4 xl:grid-cols-2">
            <section className="rounded-[20px] border border-[#eeeee9] bg-white p-4 shadow-xs">
              <div className="mb-3 flex items-center gap-2">
                <Icon name="ri-bar-chart-line" className="size-4 text-[#36533a]" />
                <h3 className="text-sm font-semibold text-black">
                  Top vùng AOI theo thời lượng
                </h3>
              </div>
              <AoiBarChart aois={data.byAoi} totalMs={data.totals.trackedDurationMs} />
            </section>

            <section className="rounded-[20px] border border-[#eeeee9] bg-white p-4 shadow-xs">
              <div className="mb-3 flex items-center gap-2">
                <Icon name="ri-stack-line" className="size-4 text-[#36533a]" />
                <h3 className="text-sm font-semibold text-black">
                  Cơ cấu theo bài học
                </h3>
              </div>
              <AoiCompositionChart lessons={data.byLesson} byAoi={data.byAoi} />
            </section>

            {scope === "cohort" && data.byStudent.length > 1 && (
              <section className="rounded-[20px] border border-[#eeeee9] bg-white p-4 shadow-xs">
                <div className="mb-3 flex items-center gap-2">
                  <Icon name="ri-group-line" className="size-4 text-[#36533a]" />
                  <h3 className="text-sm font-semibold text-black">
                    So sánh học viên
                  </h3>
                </div>
                <StudentCompareChart
                  students={data.byStudent}
                  byAoi={data.byAoi}
                />
              </section>
            )}

            {data.byVisit.length > 1 && (
              <section className="rounded-[20px] border border-[#eeeee9] bg-white p-4 shadow-xs">
                <div className="mb-3 flex items-center gap-2">
                  <Icon name="ri-history-line" className="size-4 text-[#36533a]" />
                  <h3 className="text-sm font-semibold text-black">
                    Xu hướng theo ca học
                  </h3>
                </div>
                <VisitTrendChart visits={data.byVisit} />
              </section>
            )}

            <HeatmapSection
              courseId={courseId}
              query={query}
              lessons={heatmapLessons}
            />

            <section className="rounded-[20px] border border-[#eeeee9] bg-white p-4 shadow-xs xl:col-span-2">
              <div className="mb-3 flex items-center gap-2">
                <Icon name="ri-table-line" className="size-4 text-[#36533a]" />
                <h3 className="text-sm font-semibold text-black">
                  Bảng chi tiết theo AOI
                </h3>
              </div>
              <AoiTable rows={data.byAoi} />
            </section>
          </div>
        </>
      )}
    </div>
  );
}
