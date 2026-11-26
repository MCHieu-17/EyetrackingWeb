import { expect, test } from "@playwright/test";
import { fixtures, storageStateFor, type Role } from "./support/fixtures";

/**
 * Đi qua mọi route theo vai trò: không lỗi JS, có nội dung chính, không tràn
 * ngang trên mobile. Lưới an toàn cho redesign giao diện.
 */

type RouteCase = { name: string; role: Role | null; path: (c: string) => string; mobile?: boolean };

const ROUTES: RouteCase[] = [
  { name: "landing", role: null, path: () => "/", mobile: true },
  { name: "login", role: null, path: () => "/account/login", mobile: true },
  { name: "register", role: null, path: () => "/account/register", mobile: true },
  { name: "try", role: null, path: () => "/try", mobile: true },
  { name: "student home", role: "student", path: () => "/student", mobile: true },
  { name: "student profile", role: "student", path: () => "/student/profile", mobile: true },
  { name: "student prepare", role: "student", path: (c) => `/student/courses/${c}/prepare`, mobile: true },
  { name: "student reader", role: "student", path: (c) => `/student/courses/${c}` },
  { name: "change password", role: "student", path: () => "/account/change-password", mobile: true },
  { name: "teacher home", role: "teacher", path: () => "/teacher", mobile: true },
  { name: "teacher profile", role: "teacher", path: () => "/teacher/profile", mobile: true },
  { name: "teacher content", role: "teacher", path: (c) => `/teacher/courses/${c}?tab=content` },
  { name: "teacher info", role: "teacher", path: (c) => `/teacher/courses/${c}?tab=info` },
  { name: "teacher students", role: "teacher", path: (c) => `/teacher/courses/${c}?tab=students` },
  { name: "teacher aoi", role: "teacher", path: (c) => `/teacher/courses/${c}?tab=aoi` },
  { name: "teacher visualization", role: "teacher", path: (c) => `/teacher/courses/${c}?tab=visualization` },
  { name: "admin home", role: "admin", path: () => "/admin", mobile: true },
  { name: "admin database", role: "admin", path: () => "/admin/database" },
  { name: "admin profile", role: "admin", path: () => "/admin/profile", mobile: true },
];

// Lỗi môi trường không liên quan UI (camera headless, WS gaze). Lỗi HTTP được
// kiểm tra riêng theo URL bên dưới nên bỏ dòng console chung "Failed to load".
const IGNORED = [
  /getUserMedia|NotFoundError|NotAllowedError|Requested device not found/i,
  /WebSocket/i,
  /Failed to load resource/i,
];

// Phản hồi API lỗi là hành vi đúng của backend, không phải lỗi UI.
const EXPECTED_HTTP: Array<[number, RegExp]> = [
  [401, /\/api\/auth\/(me|refresh)/],
  [404, /\/api\/calibrations?\b/],
  [503, /\/admin\/db\//], // ADMIN_DB_URL trống (stack bench) → 503 có chủ đích
];

for (const route of ROUTES) {
  for (const form of route.mobile ? ["desktop", "mobile"] : ["desktop"]) {
    test(`${route.name} (${form})`, async ({ browser, request }) => {
      const data = fixtures();
      const viewport = form === "mobile" ? { width: 390, height: 844 } : { width: 1440, height: 900 };
      const context = await browser.newContext({
        viewport,
        storageState: route.role ? await storageStateFor(request, route.role) : undefined,
      });
      const page = await context.newPage();
      const errors: string[] = [];
      page.on("pageerror", (err) => errors.push(`pageerror: ${err.message}`));
      page.on("response", (res) => {
        const url = res.url();
        if (res.status() < 400 || !/\/(api|admin|teacher|media)\//.test(url)) return;
        if (EXPECTED_HTTP.some(([code, re]) => code === res.status() && re.test(url))) return;
        errors.push(`http ${res.status()}: ${url}`);
      });
      page.on("console", (msg) => {
        if (msg.type() === "error") errors.push(`console: ${msg.text()}`);
      });

      const response = await page.goto(route.path(data.course_id), { waitUntil: "networkidle" });
      expect(response?.status() ?? 0).toBeLessThan(400);
      await expect(page).not.toHaveURL(/\/account\/login\?next=/);
      await expect(
        page.locator("main, [data-aoi='reader-root'], h1").filter({ visible: true }).first(),
      ).toBeVisible();
      await expect(page.getByText("Đã có lỗi xảy ra")).toHaveCount(0);
      await expect(page.getByText("Không tìm thấy trang")).toHaveCount(0);

      if (form === "mobile") {
        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth - window.innerWidth,
        );
        expect(overflow, "tràn ngang trên mobile").toBeLessThanOrEqual(1);
      }

      if (route.name === "student prepare" && form === "desktop") {
        const overflow = await page.evaluate(
          () => document.documentElement.scrollHeight - window.innerHeight,
        );
        expect(overflow, "trang kiểm tra camera phải gói trong 1 màn hình").toBeLessThanOrEqual(2);
      }

      const real = errors.filter((e) => !IGNORED.some((re) => re.test(e)));
      expect(real, real.join("\n")).toEqual([]);
      await context.close();
    });
  }
}
