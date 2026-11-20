import { expect, test } from "@playwright/test";
import { fixtures, login } from "./support/fixtures";

test("teacher xem replay và tổng hợp từ dữ liệu gaze seed", async ({ page }) => {
  const data = fixtures();
  await login(page, "teacher@school.edu.vn");
  await expect(page).toHaveURL(/\/teacher/);
  await page.goto(
    `/teacher/courses/${data.course_id}?tab=visualization&mode=replay&visitId=${data.visit_id}`,
  );

  await expect(
    page.getByRole("button", { name: "Xem lại ca học" }),
  ).toBeVisible();
  await expect(page.getByText("2 lượt xem", { exact: true })).toBeVisible();
  await expect(page.getByText("20 gaze", { exact: true })).toBeVisible();
  await expect(page.getByText("Đang tải mẫu gaze…")).toBeHidden({
    timeout: 15_000,
  });

  await page.getByRole("button", { name: "Tổng hợp" }).click();
  await expect(
    page.getByRole("heading", { name: "Bản đồ nhiệt theo slide" }),
  ).toBeVisible();
  await expect(page.getByLabel("Lưới heatmap 24x24")).toBeVisible();
  await expect(page.getByText(/10 mẫu trong slide/)).toBeVisible();
});
