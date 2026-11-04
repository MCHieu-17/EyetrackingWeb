"use client";

import { CourseToggle } from "@/components/teacher/course-toggle";

/**
 * Công tắc "Bắt buộc hiệu chỉnh điểm nhìn" — thiết lập cấp KHÓA HỌC.
 * Tắt = sinh viên vào thẳng trang học, không bật camera và không ghi gaze.
 */
export function CourseCalibrationToggle({
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
      icon="ri-focus-2-line"
      title="Bắt buộc hiệu chỉnh điểm nhìn"
      description="Bật: sinh viên phải hiệu chỉnh camera trước khi học. Tắt: vào học ngay, không ghi gaze."
      checked={checked}
      disabled={disabled}
      busy={busy}
      onChange={onChange}
      ariaLabel="Bắt buộc hiệu chỉnh điểm nhìn cho cả khóa học"
    />
  );
}
