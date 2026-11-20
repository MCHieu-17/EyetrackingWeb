import { expect, test } from "@playwright/test";
import { fixtures, login } from "./support/fixtures";

test("student đọc slide, làm quiz và xem kết quả", async ({ page }) => {
  const data = fixtures();
  await login(page, "student@school.edu.vn");
  await expect(page).toHaveURL(/\/student/);

  await page.getByText(data.title, { exact: true }).first().click();
  await expect(page.getByRole("heading", { name: "Bài giảng E2E" })).toBeVisible();

  await page.getByRole("button", { name: "Sau" }).click();
  await expect(page.getByText(/2\s*\/\s*2/)).toBeVisible();
  await page.getByRole("button", { name: "Trước" }).click();
  await expect(page.getByText(/1\s*\/\s*2/)).toBeVisible();

  await page.getByRole("button", { name: /Bài tập E2E/ }).click();

  // Seed cũ có thể đang ở màn review; bắt đầu lượt mới để test idempotent.
  const retry = page.getByRole("button", { name: "Làm lại", exact: true });
  if (await retry.isVisible().catch(() => false)) {
    await retry.click();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Làm lại", exact: true })
      .click();
  }

  await expect(page.getByText("1 + 1 bằng mấy?")).toBeVisible();
  await page.getByText("2", { exact: true }).click();
  await page.getByRole("button", { name: "Nộp bài" }).click();

  await expect(page.getByText(/1\/1 điểm/)).toBeVisible();
  await expect(page.getByText("Đáp án đúng").first()).toBeVisible();
  await page.getByRole("button", { name: "Làm lại", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Làm lại bài tập?" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Giữ kết quả" }).click();
});
