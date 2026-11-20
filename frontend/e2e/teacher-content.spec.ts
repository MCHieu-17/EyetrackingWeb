import { expect, test } from "@playwright/test";
import { deleteCourse, login } from "./support/fixtures";

test("teacher tạo khóa, thêm chương/bài và thấy checklist xuất bản", async ({
  page,
  request,
}) => {
  const title = `E2E Draft ${Date.now()}`;
  await login(page, "teacher@school.edu.vn");
  await expect(page).toHaveURL(/\/teacher/);

  await page.getByRole("link", { name: "Tạo khóa học" }).click();
  await page.fill("#new-course-title", title);
  await page.fill("#new-course-description", "Mô tả E2E");
  await page.getByRole("button", { name: "Tạo khóa học", exact: true }).click();

  await expect(page).toHaveURL(/\/teacher\/courses\/[0-9a-f-]+\?tab=content/);
  const courseId = new URL(page.url()).pathname.split("/")[3];

  await page
    .getByRole("button", { name: /Thêm chương|Tạo chương đầu tiên/ })
    .click();
  await expect(
    page.getByRole("textbox", { name: "Đổi tên Chương 1" }),
  ).toHaveValue("Chương 1");

  await page.getByRole("button", { name: "Thêm nội dung" }).first().click();
  await page.getByRole("menuitem", { name: "Bài giảng (PDF)" }).click();
  await expect(
    page.getByRole("textbox", { name: "Tên bài giảng" }),
  ).toBeVisible();

  await page
    .getByRole("button", { name: "Xuất bản", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Kiểm tra trước khi xuất bản" }),
  ).toBeVisible();
  await expect(page.getByText(/chưa có tài liệu PDF/).first()).toBeVisible();
  await page.keyboard.press("Escape");

  await page.getByRole("link", { name: "Thông tin" }).click();
  const toggle = page.getByRole("switch", {
    name: "Bắt buộc hiệu chỉnh điểm nhìn cho cả khóa học",
  });
  await expect(toggle).toBeVisible();
  if (await toggle.isChecked()) {
    await toggle.click();
  }
  await expect(
    page.getByText("Đã tắt bắt buộc hiệu chỉnh."),
  ).toBeVisible();

  await page.getByRole("link", { name: "Học viên" }).click();
  await page.getByRole("button", { name: /Thêm học viên/ }).first().click();
  await expect(
    page.getByRole("heading", { name: "Thêm học viên vào khóa học" }),
  ).toBeVisible();
  await page.keyboard.press("Escape");

  await deleteCourse(request, courseId);
});
