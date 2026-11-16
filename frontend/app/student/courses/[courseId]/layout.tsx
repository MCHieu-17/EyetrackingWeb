import type { ReactNode } from "react";
import type { Viewport } from "next";

// Trang học/calibration phụ thuộc trực tiếp vào hình học viewport. Khoá zoom
// trên mobile là best-effort: trình duyệt có thể bỏ qua vì lý do trợ năng,
// nhưng kết hợp với display guard để không ghi gaze khi hiển thị lệch.
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export default function StudentCourseLayout({
  children,
}: {
  children: ReactNode;
}) {
  return children;
}
