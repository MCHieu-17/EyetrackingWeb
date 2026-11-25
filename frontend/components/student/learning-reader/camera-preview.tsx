"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { Icon } from "@/components/ui/icon";

const STORAGE_KEY = "gazeedu:camera-preview-pos.v1";
const WIDTH = 160;
const HEIGHT = 120;
const MARGIN = 8;
/** Chừa chỗ cho thanh điều hướng slide ở đáy trình đọc. */
const DEFAULT_BOTTOM = 96;

type Pos = { x: number; y: number };

function clampPos(pos: Pos): Pos {
  const maxX = Math.max(MARGIN, window.innerWidth - WIDTH - MARGIN);
  const maxY = Math.max(MARGIN, window.innerHeight - HEIGHT - MARGIN);
  return {
    x: Math.min(Math.max(MARGIN, pos.x), maxX),
    y: Math.min(Math.max(MARGIN, pos.y), maxY),
  };
}

function defaultPos(): Pos {
  return clampPos({
    x: window.innerWidth - WIDTH - 16,
    y: window.innerHeight - HEIGHT - DEFAULT_BOTTOM,
  });
}

function readStoredPos(): Pos | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (
      typeof parsed === "object" &&
      parsed !== null &&
      typeof (parsed as Pos).x === "number" &&
      typeof (parsed as Pos).y === "number"
    ) {
      return clampPos(parsed as Pos);
    }
  } catch {
    /* localStorage/JSON lỗi: dùng vị trí mặc định */
  }
  return null;
}

function persistPos(pos: Pos): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(pos));
  } catch {
    /* chế độ riêng tư chặn storage: bỏ qua, khung vẫn kéo được */
  }
}

/**
 * Khung xem trước camera nhỏ, kéo được, dùng lại đúng `MediaStream` mà gaze
 * tracker đã mở để ghi gaze (không mở camera lần hai, không suy luận thêm).
 *
 * Vị trí lưu theo trình duyệt; chỉ state nội bộ component thay đổi khi kéo nên
 * trình đọc không re-render theo từng `pointermove`.
 */
export function CameraPreview({
  stream,
  visible,
}: {
  stream: MediaStream | null;
  visible: boolean;
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const boxRef = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef<{ dx: number; dy: number; pointerId: number } | null>(null);
  // Đọc vị trí đã lưu ngay lần render client đầu tiên. Server luôn trả null vì
  // khung chỉ được render khi đã có MediaStream (chỉ tồn tại ở client).
  const [pos, setPos] = useState<Pos | null>(() =>
    typeof window === "undefined" ? null : readStoredPos() ?? defaultPos(),
  );

  const active = visible && stream !== null;

  // Thu nhỏ cửa sổ có thể làm vị trí cũ rơi ra ngoài viewport.
  useEffect(() => {
    if (!visible) return;
    const onResize = () =>
      setPos((current) => (current ? clampPos(current) : current));
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [visible]);

  // Gắn cùng track camera đang phục vụ gaze; cleanup chỉ gỡ tham chiếu.
  useEffect(() => {
    const video = videoRef.current;
    if (!video || !active) return;
    video.srcObject = stream;
    void video.play().catch(() => undefined);
    return () => {
      if (video.srcObject === stream) video.srcObject = null;
    };
  }, [stream, active]);

  const commit = useCallback((next: Pos) => {
    const clamped = clampPos(next);
    setPos(clamped);
    persistPos(clamped);
  }, []);

  const onPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return;
    const rect = boxRef.current?.getBoundingClientRect();
    if (!rect) return;
    event.preventDefault();
    dragRef.current = {
      dx: event.clientX - rect.left,
      dy: event.clientY - rect.top,
      pointerId: event.pointerId,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const onPointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    setPos(clampPos({ x: event.clientX - drag.dx, y: event.clientY - drag.dy }));
  };

  const endDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    dragRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    commit({ x: event.clientX - drag.dx, y: event.clientY - drag.dy });
  };

  const onKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    const step = event.shiftKey ? 32 : 16;
    const deltas: Record<string, Pos> = {
      ArrowLeft: { x: -step, y: 0 },
      ArrowRight: { x: step, y: 0 },
      ArrowUp: { x: 0, y: -step },
      ArrowDown: { x: 0, y: step },
    };
    const delta = deltas[event.key];
    if (!delta) return;
    event.preventDefault();
    commit({
      x: (pos?.x ?? 0) + delta.x,
      y: (pos?.y ?? 0) + delta.y,
    });
  };

  if (!active) return null;

  return (
    <div
      ref={boxRef}
      role="group"
      tabIndex={0}
      aria-label="Xem trước camera. Kéo hoặc dùng phím mũi tên để di chuyển."
      title="Kéo để di chuyển"
      className="fixed z-40 cursor-grab touch-none select-none overflow-hidden rounded-xl border border-white/30 bg-black shadow-[0_8px_24px_rgba(0,0,0,0.25)] outline-none focus-visible:ring-2 focus-visible:ring-white/80 active:cursor-grabbing"
      style={{
        width: WIDTH,
        height: HEIGHT,
        ...(pos
          ? { left: pos.x, top: pos.y }
          : { right: 16, bottom: DEFAULT_BOTTOM }),
      }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={endDrag}
      onPointerCancel={endDrag}
      onKeyDown={onKeyDown}
    >
      <video
        ref={videoRef}
        muted
        playsInline
        autoPlay
        disablePictureInPicture
        className="pointer-events-none h-full w-full scale-x-[-1] object-cover"
      />
      <span className="pointer-events-none absolute inset-x-0 top-0 flex items-center gap-1 bg-gradient-to-b from-black/60 to-transparent px-2 py-1 text-[10px] font-medium text-white/90">
        <Icon name="ri-camera-line" className="size-3" />
        Camera của bạn
      </span>
    </div>
  );
}
