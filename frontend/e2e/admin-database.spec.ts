import { expect, test, type Page } from "@playwright/test";

const PASSWORD = process.env.E2E_PASSWORD || "Password123!";

async function loginAsAdmin(page: Page) {
  await page.goto("/account/login");
  await page.fill("#login-email", "admin@school.edu.vn");
  await page.fill("#login-password", PASSWORD);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await page.waitForURL(/\/admin/);
}

test("admin sử dụng trang truy vấn CSDL", async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto("/admin/database");

  await expect(
    page.getByRole("heading", { name: "Truy vấn cơ sở dữ liệu" }),
  ).toBeVisible();
  await expect(
    page.getByText("Chế độ chỉ đọc", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Bảng & cột" }),
  ).toBeVisible();

  // Click bảng trong schema explorer để sinh SELECT.
  await page.getByRole("button", { name: /^users / }).click();
  const editor = page.getByLabel("Câu lệnh SQL");
  await expect(editor).toHaveValue(/FROM "public"\."users"/);

  // Chạy câu lệnh vừa sinh.
  await page.getByRole("button", { name: "Chạy truy vấn" }).click();
  await expect(
    page.getByRole("table", { name: "Kết quả truy vấn" }),
  ).toBeVisible();
  await expect(page.getByText("admin@school.edu.vn").first()).toBeVisible();

  // Click một ô để xem giá trị đầy đủ.
  await page.getByRole("button", { name: /admin@school\.edu\.vn/ }).first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");

  // Xem tab ví dụ.
  await page.getByRole("tab", { name: "Ví dụ" }).click();
  await expect(page.getByText("Người dùng mới nhất")).toBeVisible();
  await expect(page.getByText("Khóa học & sĩ số")).toBeVisible();

  // Câu lệnh ghi bị chặn.
  await editor.fill("INSERT INTO roles (code) VALUES ('x')");
  await page.getByRole("button", { name: "Chạy truy vấn" }).click();
  const resultsPanel = page.getByRole("tabpanel", { name: "Kết quả" });
  await expect(resultsPanel.getByText("Không chạy được truy vấn")).toBeVisible();
  await expect(
    resultsPanel.getByText("Chỉ cho phép câu lệnh SELECT hoặc WITH."),
  ).toBeVisible();

  // Lỗi SQL hiển thị rõ ràng.
  await editor.fill("SELECT * FROM does_not_exist");
  await page.getByRole("button", { name: "Chạy truy vấn" }).click();
  await expect(resultsPanel.getByText("Không chạy được truy vấn")).toBeVisible();
  await expect(
    resultsPanel.getByText("Bảng không tồn tại hoặc bạn không có quyền đọc."),
  ).toBeVisible();

  // Lịch sử ghi nhận các lần chạy.
  await page.getByRole("tab", { name: /Lịch sử/ }).click();
  await expect(page.getByText("truy vấn gần nhất")).toBeVisible();
});

test("admin duyệt bảng với bộ lọc và chọn cột", async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto("/admin/database");
  await page.getByRole("tab", { name: "Duyệt bảng" }).click();

  await expect(page.getByText("Chọn bảng để duyệt dữ liệu")).toBeVisible();

  await page.getByLabel("Chọn bảng").selectOption("public.users");
  await expect(
    page.getByRole("table", { name: "Dữ liệu bảng" }),
  ).toBeVisible();
  await expect(page.getByText("admin@school.edu.vn").first()).toBeVisible();

  // Lọc theo email.
  await page.getByRole("button", { name: "Thêm bộ lọc" }).click();
  await page.getByLabel("Cột lọc").selectOption("email");
  await page.getByLabel("Toán tử lọc").selectOption("contains");
  await page.getByLabel("Giá trị lọc").fill("admin");
  await expect(page.getByText("admin@school.edu.vn").first()).toBeVisible();
  await expect(page.getByText("teacher@school.edu.vn")).toHaveCount(0);

  // Bỏ cột status khỏi bảng.
  await page.getByRole("button", { name: /Cột \(/ }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("checkbox", { name: "status" }).uncheck();
  await page.getByRole("button", { name: "Xong" }).click();
  await expect(
    page.getByRole("columnheader", { name: /status/ }),
  ).toHaveCount(0);

  // Sắp xếp theo email giảm dần.
  await page.getByLabel("Sắp xếp theo").selectOption("email");
  await page.getByLabel("Chiều sắp xếp").selectOption("desc");
  await expect(
    page.getByRole("table", { name: "Dữ liệu bảng" }),
  ).toBeVisible();

  // Bộ lọc không có kết quả.
  await page.getByLabel("Giá trị lọc").fill("zzz-not-found");
  await expect(page.getByText("Không có dữ liệu phù hợp")).toBeVisible();
});
