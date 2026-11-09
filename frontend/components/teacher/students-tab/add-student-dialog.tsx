"use client";

import { useMemo, useState } from "react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useStudentDirectory } from "@/hooks/use-teacher";
import { addCourseStudents } from "@/lib/api/teacher";
import { initialsOf } from "@/lib/utils";

/** Dialog tìm trong danh mục sinh viên và thêm vào khóa học. */
export function AddStudentDialog({
  open,
  onOpenChange,
  courseId,
  enrolledIds,
  onAdded,
  onError,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  courseId: string;
  enrolledIds: Set<string>;
  onAdded: () => void;
  onError: (msg: string) => void;
}) {
  const [q, setQ] = useState("");
  const { data: directory = [], isLoading, isError } = useStudentDirectory(open, q);
  const [adding, setAdding] = useState<string | null>(null);

  const candidates = useMemo(() => {
    return directory.filter((candidate) => !enrolledIds.has(candidate.id));
  }, [directory, enrolledIds]);

  const add = async (id: string) => {
    setAdding(id);
    try {
      await addCourseStudents(courseId, [id]);
      onAdded();
      onOpenChange(false);
    } catch (e) {
      onError(e instanceof Error ? e.message : "Không thêm được học viên");
    } finally {
      setAdding(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[min(680px,calc(100dvh-2rem))] flex-col rounded-[20px] border-[#eeeee9] bg-white shadow-2xl">
        <DialogHeader>
          <DialogTitle>Thêm học viên vào khóa học</DialogTitle>
          <DialogDescription>
            Tìm học viên theo tên hoặc mã sinh viên rồi thêm vào khóa học.
          </DialogDescription>
        </DialogHeader>
        <div className="px-6 pb-2">
          <div className="relative">
            <Icon
              name="ri-search-line"
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
            />
            <Input
              autoFocus
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Nhập tên hoặc mã sinh viên"
              className="rounded-xl border border-[#eeeee9] bg-[#fdfdfa] pl-9 shadow-none"
              aria-label="Tìm học viên để thêm"
            />
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
          {isLoading ? (
            <div className="space-y-2 p-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-12 rounded-xl" />
              ))}
            </div>
          ) : isError ? (
            <p className="px-4 py-10 text-center text-sm text-destructive">Không tải được danh mục học viên.</p>
          ) : candidates.length === 0 ? (
            <p className="px-4 py-10 text-center text-sm text-muted-foreground">
              Không tìm thấy sinh viên phù hợp.
            </p>
          ) : (
            <ul>
              {candidates.slice(0, 50).map((candidate) => (
                <li
                  key={candidate.id}
                  className="flex items-center gap-3 rounded-2xl px-3 py-2.5 transition hover:bg-[#e8f1e6]/55"
                >
                  <Avatar className="size-9">
                    <AvatarFallback>{initialsOf(candidate.name)}</AvatarFallback>
                  </Avatar>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-foreground">{candidate.name}</p>
                    <p className="text-xs text-muted-foreground">{candidate.code}</p>
                  </div>
                  <Button size="sm" variant="outline" className="rounded-full border-black/10" disabled={adding === candidate.id} onClick={() => add(candidate.id)}>
                    {adding === candidate.id ? "Đang thêm…" : "Thêm"}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
