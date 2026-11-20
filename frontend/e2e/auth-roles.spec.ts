import { expect, test } from "@playwright/test";
import { login } from "./support/fixtures";

test.describe("auth và điều hướng theo vai trò", () => {
  test("landing có CTA đăng nhập", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByRole("link", { name: "Đăng nhập" }).first(),
    ).toBeVisible();
  });

  test("route bảo vệ chuyển về login", async ({ page }) => {
    await page.goto("/student");
    await expect(page).toHaveURL(/\/account\/login/);
  });

  test("student đăng nhập vào trang khóa học", async ({ page }) => {
    await login(page, "student@school.edu.vn");
    await expect(page).toHaveURL(/\/student/);
    await expect(
      page.getByRole("heading", { name: /Chào mừng trở lại/ }),
    ).toBeVisible();
  });

  test("teacher đăng nhập vào danh sách khóa học", async ({ page }) => {
    await login(page, "teacher@school.edu.vn");
    await expect(page).toHaveURL(/\/teacher/);
    await expect(page.getByRole("heading", { name: "Khóa học" })).toBeVisible();
  });

  test("admin đăng nhập vào trang quản trị", async ({ page }) => {
    await login(page, "admin@school.edu.vn");
    await expect(page).toHaveURL(/\/admin/);
    await expect(
      page.getByRole("heading", { name: "Nâng cấp giáo viên" }),
    ).toBeVisible();
  });
});
