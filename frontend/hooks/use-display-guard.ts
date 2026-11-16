"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getCalibrationScreenSnapshot } from "@/lib/api/calibration";
import {
  detectDisplayViolation,
  zoomPercent,
  type DisplayGuardInput,
  type DisplayGuardReason,
} from "@/lib/display-guard";

type DisplayGuardMode = "reader" | "calibration";

interface UseDisplayGuardOptions {
  enabled: boolean;
  mode: DisplayGuardMode;
}

export interface DisplayGuardState {
  blocked: boolean;
  reason: DisplayGuardReason | null;
  /** Tỷ lệ zoom hiện tại so với DPR baseline (100 = bình thường). */
  zoomPercent: number;
  recheck: () => void;
}

interface GuardSnapshot {
  blocked: boolean;
  reason: DisplayGuardReason | null;
  zoomPercent: number;
}

const SAFE_STATE: GuardSnapshot = {
  blocked: false,
  reason: null,
  zoomPercent: 100,
};

// Cả hai mode hiện dùng 500ms; bảng giúp tinh chỉnh riêng sau này mà không
// phải sửa call site.
const POLL_INTERVAL_MS: Record<DisplayGuardMode, number> = {
  calibration: 500,
  reader: 500,
};

interface ElementWithWebkitFullscreen extends Element {
  webkitRequestFullscreen?: () => Promise<void> | void;
}

function isCoarsePointer(): boolean {
  if (typeof window === "undefined") return false;
  if (typeof window.matchMedia !== "function") return false;
  try {
    return window.matchMedia("(pointer: coarse)").matches;
  } catch {
    return false;
  }
}

function hasFullscreenElement(): boolean {
  if (typeof document === "undefined") return false;
  try {
    return Boolean(document.fullscreenElement);
  } catch {
    return false;
  }
}

function readInput(baselineDpr: number): DisplayGuardInput {
  const viewport = window.visualViewport;
  return {
    dpr: window.devicePixelRatio || 1,
    baselineDpr,
    visualScale: viewport?.scale ?? 1,
    fullscreenElement: hasFullscreenElement(),
    outerWidth: window.outerWidth,
    outerHeight: window.outerHeight,
    innerWidth: window.innerWidth,
    innerHeight: window.innerHeight,
    screenWidth: window.screen?.width ?? 0,
    screenHeight: window.screen?.height ?? 0,
    screenX: Number.isFinite(window.screenX) ? window.screenX : 0,
    screenY: Number.isFinite(window.screenY) ? window.screenY : 0,
    coarsePointer: isCoarsePointer(),
  };
}

function restoreProperty(
  target: object,
  name: string,
  descriptor?: PropertyDescriptor,
): void {
  try {
    if (descriptor) {
      Object.defineProperty(target, name, descriptor);
    } else {
      Reflect.deleteProperty(target, name);
    }
  } catch {
    /* Không thể khôi phục: bỏ qua, đây chỉ là best-effort. */
  }
}

/**
 * Best-effort chặn/khôi phục Fullscreen API. Trình duyệt vẫn có thể vào toàn
 * màn hình bằng F11 hoặc menu; khi đó heuristic + overlay sẽ xử lý.
 */
function blockFullscreenApi(): () => void {
  if (typeof window === "undefined" || typeof Element === "undefined") {
    return () => {};
  }

  const proto = Element.prototype as ElementWithWebkitFullscreen;
  const requestDescriptor = Object.getOwnPropertyDescriptor(
    proto,
    "requestFullscreen",
  );
  const webkitDescriptor = Object.getOwnPropertyDescriptor(
    proto,
    "webkitRequestFullscreen",
  );

  const reject = () =>
    Promise.reject(
      new DOMException(
        "Fullscreen bị tắt khi theo dõi điểm nhìn.",
        "NotAllowedError",
      ),
    );

  try {
    Object.defineProperty(proto, "requestFullscreen", {
      configurable: true,
      writable: true,
      value: reject,
    });
    Object.defineProperty(proto, "webkitRequestFullscreen", {
      configurable: true,
      writable: true,
      value: reject,
    });
  } catch {
    /* Trình duyệt không cho ghi đè: vẫn còn heuristic + overlay. */
  }

  return () => {
    restoreProperty(proto, "requestFullscreen", requestDescriptor);
    restoreProperty(proto, "webkitRequestFullscreen", webkitDescriptor);
  };
}

/**
 * Theo dõi các thay đổi hiển thị có thể làm lệch gaze trên các trang nhạy cảm
 * (calibration + reader).
 *
 * Không hứa chặn tuyệt đối: F11 và page zoom nằm ngoài quyền kiểm soát của
 * JS. Hook chỉ chặn phím/cử chỉ khi có thể, phát hiện thay đổi DPR/kích thước
 * và báo `blocked` để caller dừng ghi gaze + hiện overlay.
 */
export function useDisplayGuard({
  enabled,
  mode,
}: UseDisplayGuardOptions): DisplayGuardState {
  const [state, setState] = useState<GuardSnapshot>(SAFE_STATE);
  const baselineDprRef = useRef<number | null>(null);

  const evaluate = useCallback(() => {
    if (!enabled || typeof window === "undefined") {
      setState((prev) =>
        prev.blocked || prev.reason ? SAFE_STATE : prev,
      );
      return;
    }

    const baselineDpr =
      baselineDprRef.current ?? (window.devicePixelRatio || 1);
    baselineDprRef.current = baselineDpr;

    const input = readInput(baselineDpr);
    const reason = detectDisplayViolation(input);
    const percent = zoomPercent(input.dpr, baselineDpr);

    setState((prev) =>
      prev.blocked === Boolean(reason) &&
      prev.reason === reason &&
      prev.zoomPercent === percent
        ? prev
        : { blocked: Boolean(reason), reason, zoomPercent: percent },
    );

    // Fullscreen API vào được (ví dụ trước khi guard mount): thoát ngay.
    if (
      hasFullscreenElement() &&
      typeof document.exitFullscreen === "function"
    ) {
      void document.exitFullscreen().catch(() => {});
    }
  }, [enabled]);

  // Baseline chỉ chụp một lần cho mỗi lần mount. DPR lúc calibration là mốc
  // đúng cho phép quy đổi gaze; nếu chưa calibration thì lấy DPR hiện tại.
  // Việc đánh giá đầu tiên do effect subscription bên dưới đảm nhận (sau mount)
  // để không setState đồng bộ trong effect.
  useEffect(() => {
    if (typeof window === "undefined" || baselineDprRef.current !== null) {
      return;
    }
    const stored = getCalibrationScreenSnapshot()?.dpr;
    const current = window.devicePixelRatio || 1;
    baselineDprRef.current = stored && stored > 0 ? stored : current;
  }, []);

  useEffect(() => {
    if (!enabled || typeof window === "undefined") return;

    // Đảm bảo baseline có giá trị kể cả khi effect trên chưa chạy (thứ tự
    // effect ổn định, nhưng giữ phòng thủ để không so sánh với 0).
    if (baselineDprRef.current === null) {
      baselineDprRef.current = window.devicePixelRatio || 1;
    }

    let disposed = false;
    // Đánh giá lần đầu sau khi mount; chạy trong microtask để React không coi
    // đây là setState đồng bộ trong effect.
    queueMicrotask(() => {
      if (!disposed) evaluate();
    });

    const onAnyChange = () => evaluate();
    const onWheel = (event: WheelEvent) => {
      // Ctrl + wheel là zoom trang trên desktop; trackpad pinch cũng gửi
      // wheel với ctrlKey=true trong Chrome.
      if (!event.ctrlKey) return;
      event.preventDefault();
      evaluate();
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey)) return;
      const key = event.key;
      // Cho phép Ctrl/Cmd + 0 để người học tự khôi phục zoom 100%.
      if (
        key !== "+" &&
        key !== "=" &&
        key !== "-" &&
        key !== "_" &&
        key !== "Add" &&
        key !== "Subtract"
      ) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      evaluate();
    };
    const onGesture = (event: Event) => {
      // Safari trackpad/touch pinch.
      event.preventDefault();
      evaluate();
    };

    const visualViewport = window.visualViewport;
    window.addEventListener("resize", onAnyChange);
    visualViewport?.addEventListener("resize", onAnyChange);
    visualViewport?.addEventListener("scroll", onAnyChange);
    document.addEventListener("fullscreenchange", onAnyChange);
    document.addEventListener("webkitfullscreenchange", onAnyChange);
    window.addEventListener("keydown", onKeyDown, true);
    window.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("gesturestart", onGesture, { passive: false });
    window.addEventListener("gesturechange", onGesture, { passive: false });
    window.addEventListener("gestureend", onGesture, { passive: false });

    const restoreFullscreen = blockFullscreenApi();
    const pollMs = POLL_INTERVAL_MS[mode];
    const timer = window.setInterval(evaluate, pollMs);

    return () => {
      disposed = true;
      window.clearInterval(timer);
      window.removeEventListener("resize", onAnyChange);
      visualViewport?.removeEventListener("resize", onAnyChange);
      visualViewport?.removeEventListener("scroll", onAnyChange);
      document.removeEventListener("fullscreenchange", onAnyChange);
      document.removeEventListener("webkitfullscreenchange", onAnyChange);
      window.removeEventListener("keydown", onKeyDown, true);
      window.removeEventListener("wheel", onWheel);
      window.removeEventListener("gesturestart", onGesture);
      window.removeEventListener("gesturechange", onGesture);
      window.removeEventListener("gestureend", onGesture);
      restoreFullscreen();
    };
  }, [enabled, evaluate, mode]);

  const recheck = useCallback(() => evaluate(), [evaluate]);

  // Khi guard tắt, luôn trả trạng thái an toàn dù state còn giữ giá trị cũ.
  if (!enabled) {
    return {
      blocked: false,
      reason: null,
      zoomPercent: 100,
      recheck,
    };
  }

  return {
    blocked: state.blocked,
    reason: state.reason,
    zoomPercent: state.zoomPercent,
    recheck,
  };
}
