import { describe, expect, it } from "vitest";
import {
  getCalibrationAgeDays,
  getCalibrationDescription,
  getCalibrationHref,
  getCameraStatus,
  getFaceStatus,
  getLearningHref,
  getPrimaryLabel,
  isReadyToCalibrate,
  isReadyToLearn,
} from "./preflight-helpers";

describe("preflight hrefs", () => {
  it("builds the learning href", () => {
    expect(getLearningHref("c1", null)).toBe("/student/courses/c1");
    expect(getLearningHref("c1", "l 1")).toBe("/student/courses/c1?lesson=l%201");
  });

  it("builds the calibration href", () => {
    expect(getCalibrationHref("c1", null)).toBe("/student/courses/c1/calibrate");
    expect(getCalibrationHref("c1", "l1")).toBe("/student/courses/c1/calibrate?lesson=l1");
  });
});

describe("getCalibrationAgeDays", () => {
  it("returns infinity without a timestamp", () => {
    expect(getCalibrationAgeDays(null)).toBe(Number.POSITIVE_INFINITY);
    expect(getCalibrationAgeDays(undefined)).toBe(Number.POSITIVE_INFINITY);
  });

  it("computes the age in days", () => {
    const now = new Date("2026-11-09T00:00:00Z").getTime();
    expect(getCalibrationAgeDays("2026-11-08T00:00:00Z", now)).toBe(1);
  });
});

describe("readiness", () => {
  it("requires camera, face and calibration", () => {
    expect(isReadyToLearn("ready", "ready", true)).toBe(true);
    expect(isReadyToLearn("ready", "ready", false)).toBe(false);
    expect(isReadyToLearn("checking", "ready", true)).toBe(false);
  });

  it("requires camera and face but no calibration", () => {
    expect(isReadyToCalibrate("ready", "ready", false)).toBe(true);
    expect(isReadyToCalibrate("ready", "ready", true)).toBe(false);
    expect(isReadyToCalibrate("ready", "not-found", false)).toBe(false);
  });
});

describe("getPrimaryLabel", () => {
  it("shows the checking label", () => {
    expect(
      getPrimaryLabel({
        cameraState: "checking",
        faceState: "idle",
        readyToLearn: false,
        readyToCalibrate: false,
      }),
    ).toBe("Đang kiểm tra camera…");
  });

  it("shows the learn label", () => {
    expect(
      getPrimaryLabel({
        cameraState: "ready",
        faceState: "ready",
        readyToLearn: true,
        readyToCalibrate: false,
      }),
    ).toBe("Bắt đầu học");
  });

  it("shows the calibrate label", () => {
    expect(
      getPrimaryLabel({
        cameraState: "ready",
        faceState: "ready",
        readyToLearn: false,
        readyToCalibrate: true,
      }),
    ).toBe("Hiệu chỉnh điểm nhìn");
  });

  it("shows the retry label", () => {
    expect(
      getPrimaryLabel({
        cameraState: "error",
        faceState: "idle",
        readyToLearn: false,
        readyToCalibrate: false,
      }),
    ).toBe("Kiểm tra lại");
  });

  it("shows the default label", () => {
    expect(
      getPrimaryLabel({
        cameraState: "idle",
        faceState: "idle",
        readyToLearn: false,
        readyToCalibrate: false,
      }),
    ).toBe("Kiểm tra camera");
  });
});

describe("status labels", () => {
  it("maps camera states", () => {
    expect(getCameraStatus("checking")).toBe("Đang kiểm tra");
    expect(getCameraStatus("ready")).toBe("Sẵn sàng");
    expect(getCameraStatus("error")).toBe("Có lỗi");
    expect(getCameraStatus("idle")).toBe("Chưa kiểm tra");
  });

  it("maps face states", () => {
    expect(getFaceStatus("checking")).toBe("Đang nhận diện");
    expect(getFaceStatus("ready")).toBe("Đã phát hiện");
    expect(getFaceStatus("not-found")).toBe("Chưa phát hiện");
    expect(getFaceStatus("error")).toBe("Có lỗi");
    expect(getFaceStatus("idle")).toBe("Chưa kiểm tra");
  });
});

describe("getCalibrationDescription", () => {
  it("describes a calibrated device", () => {
    expect(getCalibrationDescription(true, "09/11/2026 10:00")).toBe(
      "Đã hiệu chỉnh trên thiết bị này lúc 09/11/2026 10:00.",
    );
    expect(getCalibrationDescription(true, null)).toBe(
      "Đã có dữ liệu hiệu chỉnh trên thiết bị này.",
    );
  });

  it("describes a stale calibration", () => {
    expect(getCalibrationDescription(false, "09/11/2026 10:00")).toBe(
      "Có bản ghi hiệu chỉnh lúc 09/11/2026 10:00, nhưng cần phiên cục bộ mới để theo dõi.",
    );
    expect(getCalibrationDescription(false, null)).toBe(
      "Cần tạo phiên hiệu chỉnh cục bộ trước khi bắt đầu theo dõi.",
    );
  });
});
