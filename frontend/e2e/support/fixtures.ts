import fs from "node:fs";
import path from "node:path";
import { expect, type APIRequestContext, type Page } from "@playwright/test";

const PASSWORD = process.env.E2E_PASSWORD || "Password123!";

export interface Fixtures {
  course_id: string;
  module_id: string;
  lesson_id: string;
  quiz_id: string;
  enrollment_id: string;
  visit_id: string;
  slide_ids: string[];
  view_ids: string[];
  title: string;
}

export function fixtures(): Fixtures {
  const file = path.join(__dirname, "..", ".fixtures.json");
  if (!fs.existsSync(file)) {
    throw new Error(
      "Thiếu frontend/e2e/.fixtures.json — chạy ./scripts/seed_e2e.py trước",
    );
  }
  return JSON.parse(fs.readFileSync(file, "utf8")) as Fixtures;
}

export async function login(page: Page, email: string): Promise<void> {
  await page.goto("/account/login");
  await page.fill("#login-email", email);
  await page.fill("#login-password", PASSWORD);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
}

async function bearer(
  request: APIRequestContext,
  email: string,
): Promise<string> {
  const response = await request.post("/api/auth/login", {
    data: { email, password: PASSWORD },
  });
  expect(response.ok()).toBeTruthy();
  const body = await response.json();
  return body.accessToken as string;
}

export async function deleteCourse(
  request: APIRequestContext,
  courseId: string,
  email = "teacher@school.edu.vn",
): Promise<void> {
  const token = await bearer(request, email);
  await request.delete(`/teacher/courses/${courseId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}
