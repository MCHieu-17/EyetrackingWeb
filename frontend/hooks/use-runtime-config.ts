"use client";

import { useQuery } from "@tanstack/react-query";
import { DEFAULT_GAZE_FPS, fetchRuntimeConfig } from "@/lib/api/config";
import { queryKeys } from "@/lib/query-keys";

/**
 * Cấu hình runtime lấy từ backend (`GET /api/config`).
 *
 * Hook luôn trả FPS hợp lệ: trong lúc tải hoặc khi fetch lỗi dùng fallback để
 * tracker khởi động ngay. Config về muộn chỉ cập nhật ref của tracker, không
 * làm WebSocket reconnect giữa phiên.
 */
export function useRuntimeConfig(): { gazeFps: number } {
  const { data } = useQuery({
    queryKey: queryKeys.config.runtime,
    queryFn: fetchRuntimeConfig,
    staleTime: Infinity,
    retry: 1,
  });
  return { gazeFps: data?.gazeFps ?? DEFAULT_GAZE_FPS };
}
