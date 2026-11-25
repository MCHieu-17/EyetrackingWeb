/**
 * Theme sáng/tối/hệ thống cho Fovea, không phụ thuộc thư viện ngoài.
 *
 * - Lựa chọn lưu ở localStorage[THEME_STORAGE_KEY] ("light" | "dark" | "system").
 * - Script inline trong <head> (THEME_INIT_SCRIPT) gắn class `.dark` trước khi
 *   paint để không nhấp nháy sai theme.
 * - Trang thu gaze (học bài, hiệu chuẩn) luôn sáng: độ sáng màn hình ảnh hưởng
 *   tới ảnh webcam, nên không để theme tối làm lệch dữ liệu.
 */
export type ThemePreference = "light" | "dark" | "system";

export const THEME_STORAGE_KEY = "fovea-theme";
export const THEME_EVENT = "fovea-theme-change";

/** Route luôn ở theme sáng (trang thu gaze: học bài, hiệu chuẩn, trải nghiệm thử). */
const FORCED_LIGHT = /^\/(student\/courses\/[^/]+(\/calibrate)?|try)\/?$/;

export function isForcedLightPath(pathname: string): boolean {
  return FORCED_LIGHT.test(pathname);
}

export const THEME_INIT_SCRIPT = `(function(){try{var p=localStorage.getItem(${JSON.stringify(
  THEME_STORAGE_KEY,
)})||"system";var f=${FORCED_LIGHT.toString()}.test(location.pathname);var d=!f&&(p==="dark"||(p==="system"&&matchMedia("(prefers-color-scheme: dark)").matches));document.documentElement.classList.toggle("dark",d);}catch(e){}})();`;

export function readThemePreference(): ThemePreference {
  if (typeof window === "undefined") return "system";
  try {
    const value = window.localStorage.getItem(THEME_STORAGE_KEY);
    return value === "light" || value === "dark" ? value : "system";
  } catch {
    return "system";
  }
}

function systemPrefersDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

/** Áp class `.dark` theo lựa chọn + route hiện tại. */
export function applyTheme(preference: ThemePreference, pathname = window.location.pathname): void {
  const dark =
    !isForcedLightPath(pathname) &&
    (preference === "dark" || (preference === "system" && systemPrefersDark()));
  const root = document.documentElement;
  if (root.classList.contains("dark") === dark) return;
  root.classList.add("theme-transition");
  root.classList.toggle("dark", dark);
  window.setTimeout(() => root.classList.remove("theme-transition"), 220);
}

export function setThemePreference(preference: ThemePreference): void {
  try {
    if (preference === "system") window.localStorage.removeItem(THEME_STORAGE_KEY);
    else window.localStorage.setItem(THEME_STORAGE_KEY, preference);
  } catch {
    // localStorage bị chặn: vẫn áp theme cho phiên hiện tại.
  }
  applyTheme(preference);
  window.dispatchEvent(new CustomEvent(THEME_EVENT, { detail: preference }));
}
