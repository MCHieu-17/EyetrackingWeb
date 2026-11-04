"use client";

import { CourseToggle } from "@/components/teacher/course-toggle";

/**
 * Công tắc "Hiển thị điểm nhìn cho sinh viên" — thiết lập cấp KHÓA HỌC.
 * Bật là áp cho mọi bài giảng và bài tập của khóa (một nguồn sự thật duy nhất).
 */
export function CourseGazeDotToggle({
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
      icon="ri-eye-line"
      title="Hiển thị điểm nhìn cho sinh viên"
      description="Sinh viên thấy chấm điểm nhìn của mình ở mọi bài giảng và bài tập."
      checked={checked}
      disabled={disabled}
      busy={busy}
      onChange={onChange}
      ariaLabel="Hiển thị điểm nhìn cho sinh viên cho cả khóa học"
    />
  );
}
