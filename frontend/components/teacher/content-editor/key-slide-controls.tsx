"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { deleteSlide, setSlideKey } from "@/lib/api/teacher";
import type { SlideAdmin } from "@/lib/types/domain";

/**
 * "Cài đặt nâng cao" của bài giảng: đánh dấu trang trọng tâm + xóa slide.
 * Danh sách slide do trình soạn truyền xuống để không gọi API hai lần.
 */
export function KeySlideControls({
  lessonId,
  canDelete,
  slides,
}: {
  lessonId: string;
  canDelete: boolean;
  slides: SlideAdmin[];
}) {
  const queryClient = useQueryClient();
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [slideToDelete, setSlideToDelete] = useState<{ id: string; orderIndex: number } | null>(null);
  const [toggleError, setToggleError] = useState("");

  const toggle = async (slideId: string, isKey: boolean) => {
    setPendingId(slideId);
    setToggleError("");
    try {
      await setSlideKey(slideId, !isKey);
      await queryClient.invalidateQueries({ queryKey: ["teacher", "lesson-slides", lessonId] });
    } catch (error) {
      setToggleError(error instanceof Error ? error.message : "Không cập nhật được slide trọng tâm.");
    } finally {
      setPendingId(null);
    }
  };

  const removeSlide = async () => {
    if (!slideToDelete) return;
    const slide = slideToDelete;
    setPendingId(slide.id);
    setToggleError("");
    try {
      await deleteSlide(slide.id);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["teacher", "lesson-slides", lessonId] }),
        queryClient.invalidateQueries({ queryKey: ["teacher", "course-tree"] }),
        queryClient.invalidateQueries({ queryKey: ["teacher", "courses"] }),
      ]);
      setSlideToDelete(null);
    } catch (error) {
      setToggleError(error instanceof Error ? error.message : "Không xóa được slide.");
    } finally {
      setPendingId(null);
    }
  };

  if (slides.length === 0) return null;

  return (
    <>
      <section className="mt-8 border-t border-black/10 pt-8">
        <div>
          <h5 className="text-sm font-semibold text-black">Trang trọng tâm</h5>
          <p className="mt-1 text-sm leading-6 text-black/45">
            Đánh dấu trang trọng tâm để tính điểm hoàn thành bài học. Trang trọng tâm có trọng số
            cao hơn trang thường.
          </p>
        </div>

        <div className="mt-5">
          <ul className="grid gap-2 md:grid-cols-2">
            {slides.map((slide) => (
              <li
                key={slide.id}
                className="grid gap-4 rounded-[18px] border border-[#eeeee9] bg-white p-4 shadow-xs sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"
              >
                <label className="flex min-w-0 cursor-pointer items-center gap-3">
                  <input
                    type="checkbox"
                    checked={slide.isKey}
                    disabled={pendingId === slide.id}
                    onChange={() => void toggle(slide.id, slide.isKey)}
                    className="size-4 accent-primary"
                  />
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium text-black">
                      Trang {slide.orderIndex}
                    </span>
                    <span className="mt-1 block text-xs text-black/40">
                      {slide.isKey ? "Slide trọng tâm" : "Slide thường"}
                    </span>
                  </span>
                </label>
                <div className="flex items-center gap-2 sm:justify-end">
                  {canDelete && (
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      disabled={pendingId === slide.id}
                      onClick={() => setSlideToDelete({ id: slide.id, orderIndex: slide.orderIndex })}
                      aria-label={`Xóa slide trang ${slide.orderIndex}`}
                      className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                    >
                      <Icon name="ri-delete-bin-line" className="size-4" />
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
        {toggleError && (
          <p role="alert" className="mt-3 text-sm text-destructive">
            {toggleError}
          </p>
        )}
      </section>
      <ConfirmDialog
        open={slideToDelete !== null}
        onOpenChange={(open) => !open && setSlideToDelete(null)}
        title={slideToDelete ? `Xóa slide trang ${slideToDelete.orderIndex}?` : "Xóa slide?"}
        description="Slide sẽ bị xóa khỏi bài học. Thao tác có thể thất bại nếu slide đã có dữ liệu theo dõi."
        confirmLabel="Xóa slide"
        destructive
        onConfirm={removeSlide}
      />
    </>
  );
}
