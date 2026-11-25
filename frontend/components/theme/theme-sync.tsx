"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { applyTheme, readThemePreference, THEME_EVENT } from "@/lib/theme";

/**
 * Giữ class `.dark` đúng khi điều hướng client-side (vào/ra trang thu gaze)
 * và khi hệ điều hành đổi theme lúc người dùng chọn "system".
 */
export function ThemeSync() {
  const pathname = usePathname();

  useEffect(() => {
    applyTheme(readThemePreference(), pathname);
  }, [pathname]);

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const sync = () => applyTheme(readThemePreference());
    media.addEventListener("change", sync);
    window.addEventListener("storage", sync);
    window.addEventListener(THEME_EVENT, sync);
    return () => {
      media.removeEventListener("change", sync);
      window.removeEventListener("storage", sync);
      window.removeEventListener(THEME_EVENT, sync);
    };
  }, []);

  return null;
}
