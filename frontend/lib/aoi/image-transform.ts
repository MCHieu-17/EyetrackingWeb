export interface ImageTransform {
  [key: string]: number;
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface ContainerRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

/**
 * Tính vùng ảnh PDF thực tế trong container theo đúng cách PdfPage fit ảnh:
 * scale = min(container/page) rồi canh giữa. Kết quả chuẩn hoá theo viewport
 * và có thể dùng ngay làm `imageTransform` của layout snapshot — kể cả khi
 * canvas chưa kịp vẽ xong.
 */
export function fittedImageTransform(
  container: ContainerRect,
  pageWidth: number,
  pageHeight: number,
  viewportWidth: number,
  viewportHeight: number,
): ImageTransform | null {
  if (
    !(container.width > 0) ||
    !(container.height > 0) ||
    !(pageWidth > 0) ||
    !(pageHeight > 0) ||
    !(viewportWidth > 0) ||
    !(viewportHeight > 0)
  ) {
    return null;
  }

  const scale = Math.min(
    container.width / pageWidth,
    container.height / pageHeight,
  );
  const width = pageWidth * scale;
  const height = pageHeight * scale;
  const left = container.left + (container.width - width) / 2;
  const top = container.top + (container.height - height) / 2;

  return {
    left: left / viewportWidth,
    top: top / viewportHeight,
    width: width / viewportWidth,
    height: height / viewportHeight,
  };
}
