"use client";

import { CourseToggle } from "@/components/teacher/course-toggle";

/**
 * Công tắc "Hiển thị khung camera cho sinh viên" — thiết lập cấp KHÓA HỌC.
 *
 * Khung nhỏ dùng lại luồng camera mà gaze tracker đã mở để ghi gaze, nên bật
 * cờ không mở thêm camera. Khóa tắt "Bắt buộc hiệu chỉnh" thì không có camera
 * và khung tự ẩn.
 */
export function CourseCameraPreviewToggle({
  checked,
  disabled,
  busy,
  onChange,
}: {
  checked: boolean;
  disabled?: boolean;
  busy?: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <CourseToggle
      icon="ri-camera-line"
      title="Hiển thị khung camera cho sinh viên"
      description="Sinh viên thấy khung xem trước camera nhỏ (kéo được) trong lúc học, biết camera đang quay gì."
      checked={checked}
      disabled={disabled}
      busy={busy}
      onChange={onChange}
      ariaLabel="Hiển thị khung camera cho sinh viên trong cả khóa học"
    />
  );
}
