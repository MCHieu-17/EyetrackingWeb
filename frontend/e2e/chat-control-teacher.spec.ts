import { test, expect } from "@playwright/test";
import { json, mockApi, seedAuth } from "./fixtures";

test("teacher chatbot toggle saves immediately and survives a reload", async ({ page }) => {
  const teacher = { email: "teacher@school.edu.vn", fullName: "Giáo viên", role: "teacher" as const };
  await seedAuth(page, teacher);
  await mockApi(page, { user: teacher });
  await page.goto("/teacher/courses/course-1?tab=content");
  const response = page.waitForResponse(r => r.url().endsWith("/api/assignments/quiz-python-1"));
  await page.getByRole("button", { name: "Mở Bài tập: Kiểm tra nhập môn" }).click();
  let saved = await (await response).json();
  await page.route("**/api/assignments/quiz-python-1", r => {
    if (r.request().method() === "PATCH") saved = { ...saved, ...r.request().postDataJSON() };
    return json(r, saved);
  });
  const toggle = page.getByRole("switch", { name: "Cho phép dùng chatbot khi làm bài", exact: true });
  await expect(toggle).toBeVisible();
  const before = await toggle.getAttribute("aria-checked");
  const patch = page.waitForRequest(r => r.url().endsWith("/api/assignments/quiz-python-1") && r.method() === "PATCH");
  await toggle.click();
  expect((await patch).postDataJSON()).toEqual({ allowChatbot: before !== "true" });
  await expect(toggle).toHaveAttribute("aria-checked", String(before !== "true"));
  await page.reload();
  await page.getByRole("button", { name: "Mở Bài tập: Kiểm tra nhập môn" }).click();
  await expect(toggle).toHaveAttribute("aria-checked", String(before !== "true"));
});
