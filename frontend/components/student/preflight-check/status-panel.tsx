"use client";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";
import type { CameraState, FaceState, Tone } from "./preflight-types";
import { getCameraStatus, getFaceStatus } from "./preflight-helpers";

function StatusRow({
  icon,
  label,
  description,
  status,
  tone = "neutral",
  success,
  danger,
}: {
  icon: string;
  label: string;
  description: string;
  status: string;
  tone?: Tone;
  /** Icon trạng thái kèm nhãn: check khi OK, cảnh báo khi lỗi. */
  success?: boolean;
  danger?: boolean;
}) {
  return (
    <div className="grid grid-cols-[2.25rem_minmax(0,1fr)_auto] items-start gap-3 py-4 first:pt-0 last:pb-0">
      <div
        className={cn(
          "flex size-9 items-center justify-center rounded-full",
          tone === "success" && "bg-success/10 text-success",
          tone === "danger" && "bg-destructive/10 text-destructive",
          tone === "warning" && "bg-warning/10 text-warning",
          tone === "neutral" && "bg-muted text-muted-foreground",
        )}
      >
        <Icon name={icon} className="size-4" />
      </div>
      <div className="min-w-0">
        <p className="text-sm font-medium text-foreground">{label}</p>
        <p className="mt-0.5 text-xs leading-5 text-muted-foreground">{description}</p>
      </div>
      <span className={cn(
        "mt-0.5 inline-flex shrink-0 items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium",
        tone === "success" && "bg-success/10 text-success",
        tone === "danger" && "bg-destructive/10 text-destructive",
        tone === "warning" && "bg-warning/10 text-warning",
        tone === "neutral" && "bg-muted text-foreground",
      )}>
        {success && <Icon name="ri-checkbox-circle-fill" className="size-3.5" />}
        {danger && <Icon name="ri-error-warning-line" className="size-3.5" />}
        {status}
      </span>
    </div>
  );
}

export function StatusPanel({
  cameraState,
  faceState,
  error,
  primaryLabel,
  checking,
  onPrimaryAction,
}: {
  cameraState: CameraState;
  faceState: FaceState;
  error: string | null;
  primaryLabel: string;
  checking: boolean;
  onPrimaryAction: () => void;
}) {
  return (
    <aside className="flex flex-col rounded-2xl border border-border bg-card p-5 text-card-foreground shadow-sm sm:p-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">Trạng thái</p>
          <h2 className="mt-1 font-display text-lg font-semibold tracking-tight text-foreground">Kiểm tra thiết bị</h2>
        </div>
        <span className="flex size-9 items-center justify-center rounded-full bg-accent text-accent-foreground">
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
          success={cameraState === "ready"}
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
          success={faceState === "ready"}
          danger={faceState === "not-found" || faceState === "error"}
        />
      </div>

      {error && (
        <div className="mt-4 flex items-start gap-2 rounded-xl bg-destructive/10 px-3 py-2.5 text-xs leading-5 text-destructive">
          <Icon name="ri-error-warning-line" className="mt-0.5 size-4 shrink-0" />
          <p>{error}</p>
        </div>
      )}
      <div className="mt-auto pt-6">
        <Button
          size="lg"
          onClick={onPrimaryAction}
          disabled={checking}
          className="w-full shadow-xs"
        >
          {checking && <Spinner />}
          {primaryLabel}
        </Button>
      </div>
    </aside>
  );
}
