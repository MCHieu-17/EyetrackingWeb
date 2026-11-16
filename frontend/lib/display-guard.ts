// Phát hiện trạng thái hiển thị làm lệch điểm nhìn (page zoom / pinch zoom /
// toàn màn hình). Trình duyệt không cho JS chặn tuyệt đối các thao tác này,
// nên đây chỉ là lớp phát hiện best-effort để frontend tạm dừng ghi gaze.

export type DisplayGuardReason =
  | "page_zoom"
  | "pinch_zoom"
  | "fullscreen"
  | "browser_fullscreen";

export interface DisplayGuardInput {
  dpr: number;
  /** DPR lúc calibration (hoặc lúc guard mount nếu chưa có calibration). */
  baselineDpr: number;
  /** visualViewport.scale; 1 là không pinch-zoom. */
  visualScale: number;
  /** document.fullscreenElement != null. */
  fullscreenElement: boolean;
  outerWidth: number;
  outerHeight: number;
  innerWidth: number;
  innerHeight: number;
  screenWidth: number;
  screenHeight: number;
  screenX: number;
  screenY: number;
  /** Thiết bị cảm ứng: bỏ qua heuristic cửa sổ toàn màn hình. */
  coarsePointer: boolean;
}

/** DPR lệch quá 1.5% so với baseline được coi là page zoom. */
const DPR_RELATIVE_TOLERANCE = 0.015;
/** visualViewport.scale lệch quá 1% được coi là pinch zoom. */
const VISUAL_SCALE_TOLERANCE = 0.01;
/** Dung sai hình học cửa sổ (px) khi nhận diện F11/toàn màn hình. */
const FULLSCREEN_TOLERANCE_PX = 2;

function finite(value: number): boolean {
  return Number.isFinite(value);
}

/**
 * heuristic cửa sổ toàn màn hình kiểu F11: cửa sổ phủ đúng màn hình, viewport
 * cũng cao bằng màn hình và cửa sổ nằm ở gốc toạ độ. Chỉ áp dụng cho thiết bị
 * trỏ chính xác (desktop), không áp dụng cho tablet/điện thoại.
 */
function isBrowserFullscreen(input: DisplayGuardInput): boolean {
  if (input.coarsePointer) return false;
  const values = [
    input.outerWidth,
    input.outerHeight,
    input.innerHeight,
    input.screenWidth,
    input.screenHeight,
    input.screenX,
    input.screenY,
  ];
  if (!values.every(finite)) return false;

  return (
    Math.abs(input.outerWidth - input.screenWidth) <= FULLSCREEN_TOLERANCE_PX &&
    Math.abs(input.outerHeight - input.screenHeight) <= FULLSCREEN_TOLERANCE_PX &&
    Math.abs(input.innerHeight - input.screenHeight) <= FULLSCREEN_TOLERANCE_PX &&
    Math.abs(input.screenX) <= FULLSCREEN_TOLERANCE_PX &&
    Math.abs(input.screenY) <= FULLSCREEN_TOLERANCE_PX
  );
}

/**
 * Trả về lý do đầu tiên khiến hiển thị không còn ổn định, hoặc null nếu bình
 * thường. Thứ tự ưu tiên: page zoom → pinch zoom → Fullscreen API → F11.
 */
export function detectDisplayViolation(
  input: DisplayGuardInput,
): DisplayGuardReason | null {
  if (
    finite(input.dpr) &&
    finite(input.baselineDpr) &&
    input.baselineDpr > 0 &&
    Math.abs(input.dpr - input.baselineDpr) / input.baselineDpr >
      DPR_RELATIVE_TOLERANCE
  ) {
    return "page_zoom";
  }

  if (
    finite(input.visualScale) &&
    Math.abs(input.visualScale - 1) > VISUAL_SCALE_TOLERANCE
  ) {
    return "pinch_zoom";
  }

  if (input.fullscreenElement) return "fullscreen";

  if (isBrowserFullscreen(input)) return "browser_fullscreen";

  return null;
}

/**
 * Tỷ lệ zoom hiện tại (%) so với DPR baseline. Dùng cho thông điệp overlay.
 * Dữ liệu không hợp lệ → 100 để không hiển thị con số vô nghĩa.
 */
export function zoomPercent(dpr: number, baselineDpr: number): number {
  if (!finite(dpr) || !finite(baselineDpr) || baselineDpr <= 0) return 100;
  return Math.round((dpr / baselineDpr) * 100);
}
