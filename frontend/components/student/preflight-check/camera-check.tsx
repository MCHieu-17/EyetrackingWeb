"use client";

import { type RefObject } from "react";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";
import type { CameraState, FaceState } from "./preflight-types";

export function CameraCheck({
  videoRef,
  cameraState,
  faceState,
}: {
  videoRef: RefObject<HTMLVideoElement | null>;
  cameraState: CameraState;
  faceState: FaceState;
}) {
  return (
    <section className="min-w-0 rounded-[20px] border border-border/80 bg-white p-2 shadow-sm sm:p-3">
      <div className="relative aspect-video overflow-hidden rounded-[16px] bg-[#111111]">
        <video
          ref={videoRef}
          muted
          playsInline
          autoPlay
          className={cn(
            "h-full w-full scale-x-[-1] object-cover transition-opacity duration-200",
            cameraState === "idle" || cameraState === "error" ? "opacity-0" : "opacity-100",
          )}
        />

        {(cameraState === "idle" || cameraState === "error") && (
          <div className="absolute inset-0 grid place-items-center px-6 text-center">
            <div>
              <div className="mx-auto flex size-12 items-center justify-center rounded-full border border-white/20 text-white">
                <Icon
                  name={cameraState === "error" ? "ri-error-warning-line" : "ri-camera-line"}
                  className="size-5"
                />
              </div>
              <p className="mt-4 text-sm font-medium text-white">
                {cameraState === "error" ? "Camera chưa sẵn sàng" : "Camera đang tắt"}
              </p>
              <p className="mx-auto mt-1.5 max-w-xs text-xs leading-5 text-white/55">
                {cameraState === "error"
                  ? "Kiểm tra quyền truy cập của trình duyệt rồi thử lại."
                  : "Bật camera để kiểm tra vị trí khuôn mặt trước khi vào bài."}
              </p>
            </div>
          </div>
        )}

        {cameraState === "checking" && (
          <div className="absolute inset-0 grid place-items-center bg-black/25">
            <span className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-black/70 px-3 py-1.5 text-xs font-medium text-white backdrop-blur-sm">
              <Spinner className="text-white" />
              Đang kiểm tra
            </span>
          </div>
        )}

        {(cameraState === "checking" || cameraState === "ready") && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <div
              className={cn(
                "h-[68%] max-h-[260px] w-[36%] min-w-[140px] max-w-[190px] rounded-[46%] border transition-colors",
                faceState === "ready" ? "border-white" : "border-white/40",
                (faceState === "not-found" || faceState === "error") && "border-white/70 border-dashed",
              )}
            />
          </div>
        )}

        <div className="absolute left-3 top-3 flex items-center gap-2">
          <span className="rounded-full border border-white/15 bg-black/55 px-2.5 py-1 text-[11px] font-medium text-white/75 backdrop-blur-sm">
            Xem trước trực tiếp
          </span>
        </div>

        {faceState === "ready" && (
          <div className="absolute bottom-3 left-3 inline-flex items-center gap-1.5 rounded-full bg-white px-2.5 py-1.5 text-[11px] font-medium text-black">
            <Icon name="ri-checkbox-circle-fill" className="size-3.5" />
            Khuôn mặt ổn định
          </div>
        )}
      </div>
      <div className="flex items-start gap-2 px-2 pb-1 pt-3 text-xs leading-5 text-muted-foreground">
        <Icon name="ri-lock-line" className="mt-0.5 size-4 shrink-0" />
        <p>Hình ảnh camera chỉ được xử lý trong phiên để ước lượng điểm nhìn và không được lưu lại.</p>
      </div>
    </section>
  );
}
