"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { CalibrationStage } from "@/components/calibration/calibration-stage";
import { DisplayGuardOverlay } from "@/components/display-guard/display-guard-overlay";
import { useCalibration } from "@/hooks/use-calibration";
import { useDisplayGuard } from "@/hooks/use-display-guard";

export function CalibrationFlow({ courseId }: { courseId: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const lessonId = searchParams.get("lesson");

  // Calibration là gaze-critical: zoom/fullscreen làm lệch toàn bộ mô hình.
  const displayGuard = useDisplayGuard({ enabled: true, mode: "calibration" });

  const engine = useCalibration({
    // Pause không tạo phiên gaze mới; overlay phải được xử lý xong trước.
    paused: displayGuard.blocked,
    onComplete: () => {
      const q = lessonId ? `?lesson=${encodeURIComponent(lessonId)}` : "";
      router.replace(`/student/courses/${courseId}${q}`);
    },
  });

  return (
    <main className="h-dvh w-full bg-[#111210]" aria-label="Không gian hiệu chỉnh điểm nhìn">
      <CalibrationStage engine={engine} />
      <DisplayGuardOverlay
        blocked={displayGuard.blocked}
        reason={displayGuard.reason}
        zoomPercent={displayGuard.zoomPercent}
        onRecheck={displayGuard.recheck}
      />
    </main>
  );
}
