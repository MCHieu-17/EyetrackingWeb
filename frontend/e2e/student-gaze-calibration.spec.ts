import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { fixtures, login } from "./support/fixtures";

const enabled = process.env.E2E_GAZE === "1";
const FACE = path.resolve(
  __dirname,
  "../../services/gaze/tests/fixtures/face_sample.jpg",
);

/**
 * Camera giả: ghép fixture mặt tĩnh vào canvas 960×640 rồi trả captureStream.
 * Gaze service thật vẫn chạy MediaPipe + UniGaze trên từng ảnh calibration.
 */
async function stubCamera(page: Page): Promise<void> {
  await page.route("**/__e2e__/face.jpg", (route) =>
    route.fulfill({ path: FACE, contentType: "image/jpeg" }),
  );
  await page.addInitScript(() => {
    const media = navigator.mediaDevices;
    if (!media) return;
    const original = media.getUserMedia.bind(media);
    media.getUserMedia = async (constraints?: MediaStreamConstraints) => {
      if (!constraints || constraints.video === false) {
        return original(constraints);
      }
      const image = new Image();
      image.src = "/__e2e__/face.jpg";
      await image.decode();
      const canvas = document.createElement("canvas");
      canvas.width = 960;
      canvas.height = 640;
      const context = canvas.getContext("2d");
      if (!context) throw new Error("không tạo được 2d context");
      const paint = () => {
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        requestAnimationFrame(paint);
      };
      paint();
      return canvas.captureStream(15);
    };
  });
}

test.describe("hiệu chỉnh điểm nhìn", () => {
  test.skip(!enabled, "Đặt E2E_GAZE=1 và chạy stack gaze thật");

  test("student hiệu chỉnh đủ 25 điểm rồi vào reader", async ({ page }) => {
    test.setTimeout(180_000);
    const data = fixtures();
    await stubCamera(page);
    await login(page, "student@school.edu.vn");
    await expect(page).toHaveURL(/\/student/);

    await page.goto(
      `/student/courses/${data.course_id}/calibrate?lesson=${encodeURIComponent(data.lesson_id)}`,
    );
    const dot = page.getByRole("button", { name: /Điểm hiệu chỉnh/ });
    await expect(dot).toBeVisible({ timeout: 30_000 });

    for (let index = 0; index < 25; index += 1) {
      await expect(dot).toHaveAccessibleName(
        `Điểm hiệu chỉnh ${index + 1}/25`,
        { timeout: 30_000 },
      );
      await dot.click();
      if (index < 24) {
        await expect(dot).toHaveAccessibleName(
          `Điểm hiệu chỉnh ${index + 2}/25`,
          { timeout: 30_000 },
        );
      }
    }

    await page.waitForURL(
      (url) => url.pathname === `/student/courses/${data.course_id}`,
      { timeout: 60_000 },
    );
    const sessionId = await page.evaluate(() =>
      localStorage.getItem("gaze_session_id"),
    );
    expect(sessionId).toBeTruthy();
  });
});
