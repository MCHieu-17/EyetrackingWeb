import { test, expect } from "@playwright/test";
import { open } from "node:fs/promises";
import { MODULES, TEACHER_COURSE, json, mockApi, seedAuth } from "./fixtures";

const TEACHER = {
  email: "teacher@school.edu.vn",
  fullName: "ThS. Nguyễn Văn Minh",
  role: "teacher" as const,
};

test.describe("Teacher", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page, TEACHER);
    await mockApi(page, { user: TEACHER });
  });

  test("danh sách khóa học hiển thị và tìm kiếm theo tên", async ({ page }) => {
    await page.goto("/teacher");
    await expect(page.getByRole("heading", { name: "Khóa học" })).toBeVisible();
    await expect(page.getByText("Lập trình Python cơ bản").first()).toBeVisible();
    await expect(page.getByRole("link", { name: "Tạo khóa học" })).toBeVisible();

    const search = page.getByRole("textbox", { name: "Tìm khóa học theo tên" });
    await search.fill("python");
    await expect(page.getByText("Lập trình Python cơ bản").first()).toBeVisible();
    await search.fill("khong-ton-tai");
    await expect(page.getByText("Không tìm thấy khóa học")).toBeVisible();
  });

  test("topbar bỏ pill Khóa học, chỉ còn logo", async ({ page }) => {
    await page.goto("/teacher");

    const topbar = page.getByRole("banner");
    await expect(topbar.getByRole("link", { name: "GazeEdu" })).toBeVisible();
    // Pill "Khóa học" trùng đích với logo đã bị bỏ khỏi topbar...
    await expect(topbar.getByRole("link", { name: "Khóa học" })).toHaveCount(0);
    // ...và 2 nút chết (Trợ giúp / Thông báo) cũng bị bỏ.
    await expect(topbar.getByRole("button", { name: "Trợ giúp" })).toHaveCount(0);
    await expect(topbar.getByRole("button", { name: "Thông báo" })).toHaveCount(0);
    // ...nhưng tiêu đề trang vẫn là "Khóa học" (không phải bỏ cả trang).
    await expect(page.getByRole("heading", { name: "Khóa học" })).toBeVisible();
  });

  test("workspace tab Nội dung hiển thị mục lục và trình soạn", async ({ page }) => {
    await page.goto("/teacher/courses/course-1?tab=content");
    await expect(
      page.getByRole("heading", { name: "Chương, bài giảng và bài tập" }),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Chương 1: Nhập môn", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Mở Bài 1: Giới thiệu" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Mở Bài tập: Kiểm tra nhập môn" })).toBeVisible();
    // Mục đầu tiên được mở sẵn trong trình soạn (không còn accordion lồng nhau).
    await expect(page.getByLabel("Tên bài giảng")).toHaveValue("Bài 1: Giới thiệu");
  });

  test("workspace có 4 tab và tab Thông tin lưu được thay đổi", async ({ page }) => {
    await page.goto("/teacher/courses/course-1?tab=info");
    for (const label of ["Nội dung", "Thông tin", "Học viên", "Vùng phân tích"]) {
      await expect(page.getByRole("link", { name: label, exact: true })).toBeVisible();
    }
    await expect(page.getByRole("heading", { name: "Xuất bản" })).toBeVisible();

    const request = page.waitForRequest(
      (candidate) =>
        new URL(candidate.url()).pathname === "/api/teacher/courses/course-1" &&
        candidate.method() === "PATCH",
    );
    await page.getByLabel("Tên khóa học").fill("Lập trình Python nâng cao");
    await page.getByRole("button", { name: "Lưu thay đổi" }).click();

    expect((await request).postDataJSON()).toMatchObject({ title: "Lập trình Python nâng cao" });
  });

  test("tab Vùng phân tích hiển thị editor AOI và phần tử DOM", async ({ page }) => {
    await page.goto("/teacher/courses/course-1?tab=aoi");
    await expect(
      page.getByRole("heading", { name: "Vùng phân tích (AOI)" }),
    ).toBeVisible();
    await expect(page.getByText("Phần tử DOM phát hiện")).toBeVisible();
    await expect(page.getByText("chat-user-message").first()).toBeVisible();
    await expect(page.getByText("Danh sách AOI")).toBeVisible();
  });

  test("thêm bài tập vào chương gọi API tạo", async ({ page }) => {
    await page.goto("/teacher/courses/course-1?tab=content");
    const request = page.waitForRequest(
      (candidate) =>
        candidate.url().includes("/api/teacher/modules/mod-1/quizzes") &&
        candidate.method() === "POST",
    );
    await page.getByRole("button", { name: "Thêm nội dung" }).first().click();
    await page.getByRole("menuitem", { name: "Bài tập trắc nghiệm" }).click();
    expect((await request).method()).toBe("POST");
  });

  test("thêm chương mới rồi đổi tên ngay tại mục lục", async ({ page }) => {
    await page.goto("/teacher/courses/course-1?tab=content");
    const createRequest = page.waitForRequest(
      (candidate) =>
        new URL(candidate.url()).pathname === "/api/teacher/courses/course-1/modules" &&
        candidate.method() === "POST",
    );
    await page.getByRole("button", { name: "Thêm chương" }).click();
    expect((await createRequest).postDataJSON()).toEqual({ title: "Chương 2" });

    const renameInput = page.getByLabel("Đổi tên Chương 2");
    await expect(renameInput).toBeVisible();
    await renameInput.fill("Chương mới");
    const renameRequest = page.waitForRequest(
      (candidate) =>
        new URL(candidate.url()).pathname === "/api/teacher/modules/mod-new" &&
        candidate.method() === "PATCH",
    );
    await renameInput.press("Enter");
    expect((await renameRequest).postDataJSON()).toEqual({ title: "Chương mới" });
    await expect(page.getByRole("button", { name: "Chương mới", exact: true })).toBeVisible();
  });

  test("đang soạn quiz dở mà thêm bài giảng thì hỏi trước", async ({ page }) => {
    await page.goto("/teacher/courses/course-1?tab=content");
    await page.getByRole("button", { name: "Mở Bài tập: Kiểm tra nhập môn" }).click();
    await page.getByLabel("Nội dung câu hỏi 1").fill("Câu hỏi đang sửa");

    await page.getByRole("button", { name: "Thêm nội dung" }).first().click();
    await page.getByRole("menuitem", { name: "Bài giảng (PDF)" }).click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("Còn thay đổi chưa lưu");
    await dialog.getByRole("button", { name: "Ở lại soạn tiếp" }).click();
    await expect(page.getByLabel("Nội dung câu hỏi 1")).toHaveValue("Câu hỏi đang sửa");
  });

  test("đổi tên bài tập từ header chung gọi PATCH assignment", async ({ page }) => {
    await page.goto("/teacher/courses/course-1?tab=content");
    await page.getByRole("button", { name: "Mở Bài tập: Kiểm tra nhập môn" }).click();

    const request = page.waitForRequest(
      (candidate) =>
        new URL(candidate.url()).pathname === "/api/assignments/quiz-python-1" &&
        candidate.method() === "PATCH",
    );
    const input = page.getByLabel("Tên bài tập");
    await input.fill("Bài tập đổi tên");
    await input.press("Enter");

    expect((await request).postDataJSON()).toEqual({ title: "Bài tập đổi tên" });
  });

  test("tạo khóa học mới tạo bản nháp và mở tab Nội dung", async ({ page }) => {
    let courseBody: unknown = null;
    await page.route("**/api/teacher/courses", async (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      courseBody = route.request().postDataJSON();
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: "course-new", title: "Khóa mới", status: "draft" }),
      });
    });
    await page.route("**/api/teacher/courses/course-new", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
    );

    await page.goto("/teacher/courses/c-new?new=1");
    await page.getByLabel("Tên khóa học").fill("Khóa mới");
    await page.getByLabel("Mô tả").fill("Mô tả khóa mới");
    await page.getByRole("button", { name: "Tạo khóa học" }).click();

    await expect(page).toHaveURL(/\/teacher\/courses\/course-new\?tab=content/);
    await expect(page.getByText("Chưa có chương")).toBeVisible();
    expect(courseBody).toMatchObject({
      title: "Khóa mới",
      description: "Mô tả khóa mới",
      status: "draft",
    });
  });

  test("xuất bản khóa học ngay trong tab Nội dung", async ({ page }) => {
    await page.route("**/api/teacher/courses", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          { ...TEACHER_COURSE, id: "course-new", title: "Khóa mới", status: "draft" },
        ]),
      }),
    );
    const request = page.waitForRequest(
      (candidate) =>
        new URL(candidate.url()).pathname === "/api/teacher/courses/course-new" &&
        candidate.method() === "PATCH",
    );

    await page.goto("/teacher/courses/course-new?tab=content");
    await page.getByRole("button", { name: "Xuất bản" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Xuất bản" }).click();

    expect((await request).postDataJSON()).toEqual({ status: "published" });
  });

  test("dialog thêm học viên tìm kiếm trên server", async ({ page }) => {
    await page.goto("/teacher/courses/course-1?tab=students");
    await page.getByRole("button", { name: /Thêm học viên/ }).first().click();
    const searchRequest = page.waitForRequest((request) => {
      const url = new URL(request.url());
      return url.pathname === "/api/teacher/students" && url.searchParams.get("q") === "SV003";
    });

    await page.getByRole("textbox", { name: "Tìm học viên để thêm" }).fill("SV003");

    await searchRequest;
    await expect(page.getByText("Phạm Văn Cường")).toBeVisible();
  });

  test("từ chối PDF quá lớn ngay trong trình soạn bài giảng", async ({ page }, testInfo) => {
    let uploadRequests = 0;
    await page.route("**/api/teacher/lessons/lesson-1/slides/upload", async (route) => {
      uploadRequests += 1;
      await route.fallback();
    });
    await page.goto("/teacher/courses/course-1?tab=content");
    await page.getByRole("button", { name: "Mở Bài 1: Giới thiệu" }).click();

    const oversizedPdf = testInfo.outputPath("too-large.pdf");
    const file = await open(oversizedPdf, "w");
    await file.truncate(50 * 1024 * 1024 + 1);
    await file.close();
    await page.locator('input[type="file"]').setInputFiles(oversizedPdf);

    await expect(page.getByText(/vượt quá 50MB/)).toBeVisible();
    expect(uploadRequests).toBe(0);
  });

  test("hiển thị lỗi khi tạo khóa học thất bại", async ({ page }) => {
    await page.route("**/api/teacher/courses", async (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      return route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Không tạo được khóa học" }),
      });
    });
    await page.goto("/teacher/courses/c-new?new=1");
    await page.getByLabel("Tên khóa học").fill("Khóa lỗi");
    await page.getByRole("button", { name: "Tạo khóa học" }).click();

    await expect(page.getByRole("alert").filter({ hasText: "Không tạo được khóa học" })).toBeVisible();
    await expect(page).toHaveURL(/\/teacher\/courses\/c-new/);
  });

  test("thay PDF tải lại danh sách slide quản trị", async ({ page }) => {
    let slideRequests = 0;
    await page.route("**/api/teacher/lessons/lesson-1/slides", (route) => {
      slideRequests += 1;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          { id: `slide-${slideRequests}`, orderIndex: 1, imageUrl: null, isKey: false },
        ]),
      });
    });
    await page.route("**/api/teacher/lessons/lesson-1/slides/upload", (route) =>
      route.fulfill({ status: 201, contentType: "application/json", body: '{"ok":true,"slides":1}' }),
    );
    await page.goto("/teacher/courses/course-1?tab=content");
    await page.getByRole("button", { name: "Mở Bài 1: Giới thiệu" }).click();
    await expect.poll(() => slideRequests).toBe(1);

    // Bài đã có slide → phải xác nhận trước khi thay tài liệu.
    await page.locator('input[type="file"]').setInputFiles({
      name: "replacement.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4"),
    });
    await expect(page.getByRole("dialog")).toContainText("Thay tài liệu của bài giảng?");
    await page.getByRole("button", { name: "Thay tài liệu" }).click();

    await expect.poll(() => slideRequests).toBeGreaterThan(1);
  });

  test("đổi tên bài học gọi API cập nhật", async ({ page }) => {
    await page.goto("/teacher/courses/course-1?tab=content");
    const request = page.waitForRequest(
      (candidate) =>
        candidate.url().includes("/api/teacher/lessons/lesson-1") &&
        candidate.method() === "PATCH",
    );

    const input = page.getByLabel("Tên bài giảng");
    await input.fill("Bài 1: Python nhập môn");
    await input.press("Enter");

    expect((await request).postDataJSON()).toEqual({ title: "Bài 1: Python nhập môn" });
  });

  test("bật hiển thị điểm nhìn ở tab Thông tin gọi API cập nhật khóa", async ({ page }) => {
    await page.goto("/teacher/courses/course-1?tab=info");
    const request = page.waitForRequest(
      (candidate) =>
        candidate.url().includes("/api/teacher/courses/course-1/gaze-dot") &&
        candidate.method() === "PATCH",
    );

    const toggle = page.getByRole("switch", {
      name: "Hiển thị điểm nhìn cho sinh viên cho cả khóa học",
    });
    await expect(toggle).toHaveAttribute("aria-checked", "false");
    await toggle.click();

    expect((await request).postDataJSON()).toEqual({ showGazeDot: true });
  });

  test("tắt bắt buộc hiệu chỉnh ở tab Thông tin gọi API cập nhật khóa", async ({ page }) => {
    await page.goto("/teacher/courses/course-1?tab=info");
    const request = page.waitForRequest(
      (candidate) =>
        candidate.url().includes("/api/teacher/courses/course-1/require-calibration") &&
        candidate.method() === "PATCH",
    );

    const toggle = page.getByRole("switch", {
      name: "Bắt buộc hiệu chỉnh điểm nhìn cho cả khóa học",
    });
    await expect(toggle).toHaveAttribute("aria-checked", "true");
    await toggle.click();

    expect((await request).postDataJSON()).toEqual({ requireCalibration: false });
  });

  test("kiểm tra nội dung trước khi xuất bản liệt kê mục còn thiếu", async ({ page }) => {
    await page.route("**/api/teacher/courses/**", (r) =>
      json(r, [
        {
          ...MODULES[0],
          lessons: [
            { ...MODULES[0].lessons[0], slides: 0 },
            { ...MODULES[0].lessons[2], questionCount: 0 },
          ],
        },
      ]),
    );
    await page.goto("/teacher/courses/course-1?tab=content");
    await page.getByRole("button", { name: /mục cần hoàn thiện trước khi xuất bản/ }).click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("Bài giảng chưa có tài liệu PDF");
    await expect(dialog).toContainText("Bài tập chưa có câu hỏi nào");

    // "Mở mục này" đóng hộp thoại và mở đúng mục trong trình soạn.
    await dialog.getByRole("button", { name: "Mở mục này" }).first().click();
    await expect(dialog).toHaveCount(0);
    await expect(page.getByLabel("Tên bài giảng")).toHaveValue("Bài 1: Giới thiệu");
  });

  test("bật cho phép làm lại dùng công tắc ngay đầu phần soạn bài tập", async ({ page }) => {
    await page.goto("/teacher/courses/course-1?tab=content");
    await page.getByRole("button", { name: "Mở Bài tập: Kiểm tra nhập môn" }).click();

    // Công tắc phải thấy được ngay (không nằm trong mục đang gập).
    const toggle = page.getByRole("switch", { name: /Cho phép học viên làm lại/ });
    await expect(toggle).toBeVisible();
    const before = await toggle.getAttribute("aria-checked");

    const request = page.waitForRequest(
      (candidate) =>
        candidate.url().includes("/api/assignments/quiz-python-1") &&
        candidate.method() === "PATCH",
    );
    await toggle.click();

    // Bật/tắt là lưu ngay, không cần bấm "Lưu bài tập nháp"/"Giao bài".
    expect((await request).postDataJSON()).toEqual({ allowRetry: before !== "true" });
  });

  test("lưu nháp bài tập khi còn câu hỏi dở", async ({ page }) => {
    await page.goto("/teacher/courses/course-1?tab=content");
    await page.getByRole("button", { name: "Mở Bài tập: Kiểm tra nhập môn" }).click();
    await page.getByRole("button", { name: "Thêm câu hỏi" }).click();
    // Câu 4 chưa có đáp án → không thể lưu lên server nhưng KHÔNG chặn lưu nháp.
    await page.getByLabel("Nội dung câu hỏi 4").fill("Câu hỏi mới nhưng chưa có đáp án");

    const request = page.waitForRequest(
      (candidate) =>
        candidate.url().includes("/api/assignments/quiz-python-1") &&
        candidate.method() === "PATCH",
    );
    await page.getByRole("button", { name: "Lưu bài tập nháp" }).click();

    const body = (await request).postDataJSON() as { status: string; questions: unknown[] };
    expect(body.status).toBe("draft");
    expect(body.questions).toHaveLength(3); // chỉ 3 câu hợp lệ được gửi lên
    await expect(page.getByText("1 câu chưa hoàn thiện", { exact: true })).toBeVisible();
  });

  test("chuyển mục khi còn thay đổi chưa lưu thì hỏi trước", async ({ page }) => {
    await page.goto("/teacher/courses/course-1?tab=content");
    await page.getByRole("button", { name: "Mở Bài tập: Kiểm tra nhập môn" }).click();
    await page.getByLabel("Nội dung câu hỏi 1").fill("Câu hỏi đã sửa nhưng chưa lưu");

    await page.getByRole("button", { name: "Mở Bài 1: Giới thiệu" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("Còn thay đổi chưa lưu");

    await dialog.getByRole("button", { name: "Ở lại soạn tiếp" }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    // Vẫn ở bài tập và nội dung vừa nhập còn nguyên.
    await expect(page.getByLabel("Nội dung câu hỏi 1")).toHaveValue("Câu hỏi đã sửa nhưng chưa lưu");

    // Bỏ thay đổi thì mới đổi sang mục khác.
    await page.getByRole("button", { name: "Mở Bài 1: Giới thiệu" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Bỏ thay đổi" }).click();
    await expect(page.getByLabel("Tên bài giảng")).toHaveValue("Bài 1: Giới thiệu");
  });

  test("kéo thả sắp xếp bài học và bài tập trong chương", async ({ page }) => {
    await page.goto("/teacher/courses/course-1?tab=content");
    // Không còn nút lên/xuống, chỉ còn tay kéo.
    await expect(page.getByRole("button", { name: /^Đưa .* (lên|xuống)$/ })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Kéo để sắp xếp Bài 1: Giới thiệu" })).toBeVisible();

    const request = page.waitForRequest((candidate) =>
      candidate.url().includes("/api/teacher/modules/mod-1/items/reorder"),
    );

    // Sắp xếp bằng bàn phím (cũng là đường dùng cho trình đọc màn hình).
    const handle = page.getByRole("button", { name: "Kéo để sắp xếp Bài 1: Giới thiệu" });
    await handle.focus();
    await page.keyboard.press("Space");
    // Chờ thông báo aria-live xác nhận đã "nhặt" được item trước khi di chuyển.
    await expect(page.getByText("Đang ở vị trí 1/3.")).toBeAttached();
    await page.keyboard.press("ArrowDown");
    await expect(page.getByText("Đang ở vị trí 2/3.")).toBeAttached();
    await page.keyboard.press("Space");

    // Gửi lại toàn bộ thứ tự mới của chương (bài học + bài tập dùng chung order).
    const body = (await request).postDataJSON() as { items: { id: string }[] };
    expect(body.items.map((item) => item.id)).toEqual([
      "lesson-2",
      "lesson-1",
      "lesson-quiz-1",
    ]);

    // Thứ tự hiển thị cũng phải đổi theo (fixture trả cây đã sắp xếp lại).
    const movedUp = page.getByRole("button", { name: "Kéo để sắp xếp Bài 2: Biến" });
    await expect(async () => {
      const [movedBox, originalBox] = [await movedUp.boundingBox(), await handle.boundingBox()];
      expect(movedBox!.y).toBeLessThan(originalBox!.y);
    }).toPass();
  });

  test("kéo thả bằng chuột cũng gọi API reorder", async ({ page }) => {
    await page.goto("/teacher/courses/course-1?tab=content");
    const handle = page.getByRole("button", { name: "Kéo để sắp xếp Bài 1: Giới thiệu" });
    const target = page.getByRole("button", { name: "Kéo để sắp xếp Bài 2: Biến" });
    const request = page.waitForRequest((candidate) =>
      candidate.url().includes("/api/teacher/modules/mod-1/items/reorder"),
    );

    const from = (await handle.boundingBox())!;
    const to = (await target.boundingBox())!;
    await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
    await page.mouse.down();
    // Cần vài bước di chuyển để vượt ngưỡng 6px và cập nhật vị trí thả.
    await page.mouse.move(from.x + from.width / 2, from.y + from.height, { steps: 5 });
    await page.mouse.move(to.x + to.width / 2, to.y + to.height / 2, { steps: 10 });
    await page.mouse.up();

    const body = (await request).postDataJSON() as { items: { id: string }[] };
    expect(body.items.map((item) => item.id)).toEqual([
      "lesson-2",
      "lesson-1",
      "lesson-quiz-1",
    ]);
  });

  test("workspace tab Học viên hiển thị danh sách", async ({ page }) => {
    await page.goto("/teacher/courses/course-1?tab=students");
    await expect(page.getByText("Nguyễn Văn An")).toBeVisible();
    await expect(page.getByText("Trần Thị Bình")).toBeVisible();
    await expect(page.getByRole("button", { name: /Thêm học viên/ })).toBeVisible();
  });

  test("drawer học viên hiển thị mọi bài và liên kết heatmap", async ({ page }) => {
    await page.goto("/teacher/courses/course-1?tab=students");
    await page.getByRole("button", { name: "Xem heatmap" }).first().click();

    await expect(page.getByRole("dialog").getByText("Nguyễn Văn An")).toBeVisible();
    await expect(page.getByRole("dialog").getByText("Bài 1: Giới thiệu")).toBeVisible();
    await expect(page.getByRole("dialog").getByText("Bài 2: Biến")).toBeVisible();
    await expect(page.getByRole("dialog").getByRole("link", { name: /Bài 2: Biến/ })).toHaveAttribute(
      "href",
      "/teacher/courses/course-1/lessons/lesson-2/heatmap?student=stu-1&from=students",
    );
  });

  test("heatmap viewer hiển thị bộ lọc và dữ liệu", async ({ page }) => {
    await page.goto("/teacher/courses/course-1/lessons/lesson-1/heatmap");
    await expect(page.getByText("Phân tích điểm nhìn")).toBeVisible();
    await expect(page.getByRole("combobox", { name: "Đối tượng" })).toBeVisible();
    await expect(page.getByText("Tỷ lệ gaze trên trang")).toBeVisible();
  });

  test("hồ sơ giảng viên", async ({ page }) => {
    await page.goto("/teacher/profile");
    await expect(page.getByRole("heading", { name: "ThS. Nguyễn Văn Minh" })).toBeVisible();
    await expect(page.getByText("GV001", { exact: true })).toBeVisible();
  });
});
