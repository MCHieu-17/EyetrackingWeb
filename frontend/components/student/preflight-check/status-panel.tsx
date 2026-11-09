"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";
import type { CameraState, FaceState, Tone } from "./preflight-types";
import {
  getCalibrationDescription,
  getCameraStatus,
  getFaceStatus,
} from "./preflight-helpers";

function StatusRow({
  icon,
  label,
  description,
  status,
  tone = "neutral",
}: {
  icon: string;
  label: string;
  description: string;
  status: string;
  tone?: Tone;
}) {
  return (
    <div className="grid grid-cols-[2.25rem_minmax(0,1fr)_auto] items-start gap-3 py-4 first:pt-0 last:pb-0">
      <div
        className={cn(
          "flex size-9 items-center justify-center rounded-full border",
          tone === "success" && "border-[#d8e7d5] bg-[#e8f1e6] text-[#52704f]",
          (tone === "danger" || tone === "warning") && "border-border bg-[#f5f6f2] text-foreground",
          tone === "neutral" && "border-border bg-[#f5f6f2] text-muted-foreground",
        )}
      >
        <Icon name={icon} className="size-4" />
      </div>
      <div className="min-w-0">
        <p className="text-sm font-medium text-foreground">{label}</p>
        <p className="mt-0.5 text-xs leading-5 text-muted-foreground">{description}</p>
      </div>
      <span className={cn(
        "mt-0.5 shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium",
        tone === "success" ? "bg-[#e8f1e6] text-[#52704f]" : "bg-[#f5f6f2] text-foreground",
      )}>
        {status}
      </span>
    </div>
  );
}

export function StatusPanel({
  cameraState,
  faceState,
  isCalibrated,
  calibrationTime,
  error,
  sessionIssue,
  primaryLabel,
  readyToLearn,
  checking,
  onPrimaryAction,
  calibrationHref,
}: {
  cameraState: CameraState;
  faceState: FaceState;
  isCalibrated: boolean;
  calibrationTime: string | null;
  error: string | null;
  sessionIssue: string | null;
  primaryLabel: string;
  readyToLearn: boolean;
  checking: boolean;
  onPrimaryAction: () => void;
  calibrationHref: string;
}) {
  return (
    <aside className="flex flex-col rounded-[20px] border border-border/80 bg-white p-5 shadow-sm sm:p-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">Trạng thái</p>
          <h2 className="mt-1 text-lg font-semibold tracking-tight text-foreground">Sẵn sàng vào bài</h2>
        </div>
        <span className="flex size-9 items-center justify-center rounded-full bg-[#e8f1e6] text-[#52704f]">
          <Icon name="ri-equalizer-2-line" className="size-4" />
        </span>
      </div>

      <div className="mt-6 divide-y divide-border">
        <StatusRow
          icon="ri-eye-line"
          label="Camera"
          description="Trình duyệt có thể lấy hình ảnh từ camera."
          status={getCameraStatus(cameraState)}
          tone={
            cameraState === "ready" ? "success" : cameraState === "error" ? "danger" : "neutral"
          }
        />
        <StatusRow
          icon="ri-user-line"
          label="Khuôn mặt"
          description="Khuôn mặt có thể được pipeline gaze xử lý."
          status={getFaceStatus(faceState)}
          tone={
            faceState === "ready"
              ? "success"
              : faceState === "not-found" || faceState === "error"
                ? "danger"
                : "neutral"
          }
        />
        <StatusRow
          icon="ri-focus-2-line"
          label="Hiệu chỉnh điểm nhìn"
          description={getCalibrationDescription(isCalibrated, calibrationTime)}
          status={isCalibrated ? "Phiên sẵn sàng" : "Cần hiệu chỉnh"}
          tone={isCalibrated ? "success" : "neutral"}
        />
      </div>

      {error && (
        <div className="mt-4 flex items-start gap-2 rounded-xl border border-border/80 bg-[#f5f6f2] px-3 py-2.5 text-xs leading-5 text-foreground">
          <Icon name="ri-error-warning-line" className="mt-0.5 size-4 shrink-0" />
          <p>{error}</p>
        </div>
      )}
      {sessionIssue && (
        <div className="mt-4 flex items-start gap-2 rounded-xl border border-border/80 bg-[#f5f6f2] px-3 py-2.5 text-xs leading-5 text-foreground">
          <Icon name="ri-error-warning-line" className="mt-0.5 size-4 shrink-0" />
          <p>{sessionIssue}</p>
        </div>
      )}
      <div className="mt-auto space-y-2 pt-6">
        <Button
          size="lg"
          onClick={onPrimaryAction}
          disabled={checking}
          className="w-full bg-black text-white shadow-xs hover:bg-[#292a27]"
        >
          {checking && <Spinner />}
          {readyToLearn && <Icon name="ri-play-circle-line" className="size-5" />}
          {primaryLabel}
        </Button>

        {isCalibrated && (
          <Button asChild variant="outline" size="lg" className="w-full">
            <Link href={calibrationHref}>
              <Icon name="ri-focus-2-line" />
              Hiệu chỉnh lại điểm nhìn
            </Link>
          </Button>
        )}
      </div>
    </aside>
  );
}
