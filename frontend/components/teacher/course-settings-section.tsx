"use client";

import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { CourseCalibrationToggle } from "@/components/teacher/calibration-toggle";
import { CourseCameraPreviewToggle } from "@/components/teacher/camera-preview-toggle";
import { CourseGazeDotToggle } from "@/components/teacher/gaze-dot-toggle";
import { useTeacherCourses } from "@/hooks/use-teacher";
import {
  setCourseCameraPreview,
  setCourseGazeDot,
  setCourseRequireCalibration,
} from "@/lib/api/teacher";
import { updateCourseFlag } from "./course-settings-cache";

/**
 * Khối "Thiết lập khóa học" nằm trong tab Thông tin.
 *
 * Ba công tắc áp cho toàn khóa: bắt buộc hiệu chỉnh điểm nhìn, hiển thị
 * khung camera và hiển thị chấm điểm nhìn cho sinh viên.
 */
export function CourseSettingsSection({
  courseId,
  canManage,
}: {
  courseId: string;
  canManage: boolean;
}) {
  const queryClient = useQueryClient();
  const { data: courses = [] } = useTeacherCourses();
  const course = useMemo(() => courses.find((c) => c.id === courseId), [courses, courseId]);

  const [hydratedId, setHydratedId] = useState<string | null>(null);
  const [showGazeDot, setShowGazeDot] = useState(false);
  const [showCameraPreview, setShowCameraPreview] = useState(false);
  const [requireCalibration, setRequireCalibration] = useState(true);
  const [busy, setBusy] = useState(false);
  const [cameraBusy, setCameraBusy] = useState(false);
  const [calibrationBusy, setCalibrationBusy] = useState(false);
  const [message, setMessage] = useState<{ tone: "ok" | "err"; text: string } | null>(null);

  if (course && hydratedId !== course.id) {
    setHydratedId(course.id);
    setShowGazeDot(Boolean(course.showGazeDot));
    setShowCameraPreview(Boolean(course.showCameraPreview));
    setRequireCalibration(course.requireCalibration !== false);
  }

  const toggle = async (value: boolean) => {
    setShowGazeDot(value);
    setBusy(true);
    setMessage(null);
    const error = await updateCourseFlag({
      queryClient,
      courseId,
      field: "showGazeDot",
      value,
      request: () => setCourseGazeDot(courseId, value),
    });
    if (error) setShowGazeDot(!value);
    setMessage(
      error
        ? { tone: "err", text: `Không đổi được thiết lập: ${error}` }
        : {
            tone: "ok",
            text: value
              ? "Đã bật chấm điểm nhìn cho sinh viên."
              : "Đã tắt chấm điểm nhìn.",
          },
    );
    setBusy(false);
  };

  const toggleCamera = async (value: boolean) => {
    setShowCameraPreview(value);
    setCameraBusy(true);
    setMessage(null);
    const error = await updateCourseFlag({
      queryClient,
      courseId,
      field: "showCameraPreview",
      value,
      request: () => setCourseCameraPreview(courseId, value),
    });
    if (error) setShowCameraPreview(!value);
    setMessage(
      error
        ? { tone: "err", text: `Không đổi được thiết lập: ${error}` }
        : {
            tone: "ok",
            text: value
              ? "Đã bật khung camera cho sinh viên."
              : "Đã tắt khung camera.",
          },
    );
    setCameraBusy(false);
  };

  const toggleCalibration = async (value: boolean) => {
    setRequireCalibration(value);
    setCalibrationBusy(true);
    setMessage(null);
    const error = await updateCourseFlag({
      queryClient,
      courseId,
      field: "requireCalibration",
      value,
      request: () => setCourseRequireCalibration(courseId, value),
    });
    if (error) setRequireCalibration(!value);
    setMessage(
      error
        ? { tone: "err", text: `Không đổi được thiết lập: ${error}` }
        : {
            tone: "ok",
            text: value
              ? "Đã bật bắt buộc hiệu chỉnh."
              : "Đã tắt bắt buộc hiệu chỉnh.",
          },
    );
    setCalibrationBusy(false);
  };

  return (
    <section className="space-y-3 rounded-[20px] border border-[#eeeee9] bg-white p-4 shadow-xs sm:p-5">
      <h3 className="text-base font-semibold text-black">Thiết lập khóa học</h3>

      <CourseCalibrationToggle
        checked={requireCalibration}
        disabled={!canManage}
        busy={calibrationBusy}
        onChange={(value) => void toggleCalibration(value)}
      />

      <CourseCameraPreviewToggle
        checked={showCameraPreview}
        disabled={!canManage}
        busy={cameraBusy}
        onChange={(value) => void toggleCamera(value)}
      />

      <CourseGazeDotToggle
        checked={showGazeDot}
        disabled={!canManage}
        busy={busy}
        onChange={(value) => void toggle(value)}
      />

      {!canManage && (
        <p className="text-xs text-black/60">
          Chỉ chủ khóa học hoặc quản trị viên mới đổi được thiết lập.
        </p>
      )}

      {message && (
        <Alert variant={message.tone === "ok" ? "success" : "destructive"} title={message.text} />
      )}
    </section>
  );
}
