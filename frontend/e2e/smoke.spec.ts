import { expect, test, type Page } from "@playwright/test";

const PASSWORD = process.env.E2E_PASSWORD || "Password123!";

async function login(page: Page, email: string) {
  await page.goto("/account/login");
  await page.fill("#login-email", email);
  await page.fill("#login-password", PASSWORD);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
}

test("landing page hiển thị CTA đăng nhập", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("link", { name: "Đăng nhập" }).first(),
  ).toBeVisible();
});

test("student đăng nhập và vào trang khóa học", async ({ page }) => {
  await login(page, "student@school.edu.vn");
  await page.waitForURL(/\/student/);
  await expect(
    page.getByRole("heading", { name: /Chào mừng trở lại/ }),
  ).toBeVisible();
});

test("teacher đăng nhập và vào trang quản lý khóa học", async ({ page }) => {
  await login(page, "teacher@school.edu.vn");
  await page.waitForURL(/\/teacher/);
  await expect(page.getByRole("heading", { name: "Khóa học" })).toBeVisible();
});

test("admin đăng nhập và vào trang quản trị", async ({ page }) => {
  await login(page, "admin@school.edu.vn");
  await page.waitForURL(/\/admin/);
  await expect(
    page.getByRole("heading", { name: "Nâng cấp giáo viên" }),
  ).toBeVisible();
});
