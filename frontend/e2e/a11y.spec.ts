import fs from "node:fs";
import path from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { fixtures, storageStateFor, type Role } from "./support/fixtures";

/**
 * Accessibility (axe-core) trên các trang chính.
 *
 * Không được có rule serious/critical MỚI so với e2e/a11y-baseline.json (so
 * theo rule, không theo số node vì số node đổi theo dữ liệu seed). Rule trong
 * A11Y_STRICT_RULES (vd "color-contrast") phải bằng 0 bất kể baseline.
 * Ghi lại baseline có chủ đích: UPDATE_A11Y_BASELINE=1 ./scripts/e2e.sh a11y
 */

const BASELINE = path.join(__dirname, "a11y-baseline.json");
const STRICT_RULES = (process.env.A11Y_STRICT_RULES ?? "")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);

const PAGES: Array<{ name: string; role: Role | null; path: (c: string) => string }> = [
  { name: "landing", role: null, path: () => "/" },
  { name: "login", role: null, path: () => "/account/login" },
  { name: "try", role: null, path: () => "/try" },
  { name: "student-home", role: "student", path: () => "/student" },
  { name: "student-reader", role: "student", path: (c) => `/student/courses/${c}` },
  { name: "teacher-home", role: "teacher", path: () => "/teacher" },
  { name: "teacher-content", role: "teacher", path: (c) => `/teacher/courses/${c}?tab=content` },
  { name: "teacher-visualization", role: "teacher", path: (c) => `/teacher/courses/${c}?tab=visualization` },
  { name: "admin-home", role: "admin", path: () => "/admin" },
];

type Baseline = Record<string, Record<string, number>>;

function readBaseline(): Baseline {
  return fs.existsSync(BASELINE) ? JSON.parse(fs.readFileSync(BASELINE, "utf8")) : {};
}

for (const item of PAGES) {
  test(`a11y ${item.name}`, async ({ browser, request }) => {
    const data = fixtures();
    const context = await browser.newContext({
      storageState: item.role ? await storageStateFor(request, item.role) : undefined,
    });
    const page = await context.newPage();
    await page.goto(item.path(data.course_id), { waitUntil: "networkidle" });
    await page.waitForTimeout(500);

    const result = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    const counts: Record<string, number> = {};
    for (const v of result.violations) {
      if (v.impact !== "serious" && v.impact !== "critical") continue;
      counts[v.id] = v.nodes.length;
    }
    await context.close();

    if (process.env.UPDATE_A11Y_BASELINE === "1") {
      const baseline = readBaseline();
      baseline[item.name] = counts;
      fs.writeFileSync(BASELINE, JSON.stringify(baseline, null, 2) + "\n");
      return;
    }

    const allowed = readBaseline()[item.name] ?? {};
    for (const [rule, n] of Object.entries(counts)) {
      const permitted = !STRICT_RULES.includes(rule) && rule in allowed;
      expect(permitted, `${item.name}: ${rule} (${n} node) chưa có trong baseline`).toBe(true);
    }
  });
}
