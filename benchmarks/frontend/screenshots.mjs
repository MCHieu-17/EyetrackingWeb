#!/usr/bin/env node
// Chụp ảnh các trang chính (light/dark × desktop/mobile) để so sánh UI trước/sau.
//   node benchmarks/frontend/screenshots.mjs --base http://127.0.0.1:3100 \
//     --fixtures <run>/fixtures.json --tokens <run>/.runtime/tokens.json \
//     --out <run>/frontend/screenshots
// Không phải test: chỉ ghi PNG + index.json để người duyệt xem bằng mắt.
import fs from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, "../../frontend");
const require = createRequire(path.join(FRONTEND, "package.json"));
const { chromium } = require("playwright");

function arg(name, fallback = "") {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 ? process.argv[i + 1] : fallback;
}

const BASE = arg("base", process.env.BENCH_BASE_URL || "http://127.0.0.1:3100");
const OUT = path.resolve(arg("out", "screenshots"));
const fixtures = JSON.parse(fs.readFileSync(arg("fixtures"), "utf8"));
const tokens = JSON.parse(fs.readFileSync(arg("tokens"), "utf8"));
const course = fixtures.ids.core_course_id;

// Khóa localStorage của theme; frontend cũ bỏ qua, frontend mới đọc khóa này.
const THEME_KEY = "fovea-theme";

const PAGES = [
  ["home", null, "/"],
  ["login", null, "/account/login"],
  ["register", null, "/account/register"],
  ["try", null, "/try"],
  ["student_home", "student", "/student"],
  ["student_profile", "student", "/student/profile"],
  ["student_prepare", "student", `/student/courses/${course}/prepare`],
  ["student_reader", "student", `/student/courses/${course}`],
  ["teacher_home", "teacher", "/teacher"],
  ["teacher_content", "teacher", `/teacher/courses/${course}?tab=content`],
  ["teacher_info", "teacher", `/teacher/courses/${course}?tab=info`],
  ["teacher_students", "teacher", `/teacher/courses/${course}?tab=students`],
  ["teacher_aoi", "teacher", `/teacher/courses/${course}?tab=aoi`],
  ["teacher_visualization", "teacher", `/teacher/courses/${course}?tab=visualization`],
  ["admin_home", "admin", "/admin"],
  ["admin_database", "admin", "/admin/database"],
];

const VIEWPORTS = {
  desktop: { width: 1440, height: 900 },
  mobile: { width: 390, height: 844 },
};

const only = arg("only") ? new Set(arg("only").split(",")) : null;
const host = new URL(BASE).hostname;

fs.mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch();
const index = [];
try {
  for (const theme of ["light", "dark"]) {
    for (const [form, viewport] of Object.entries(VIEWPORTS)) {
      for (const [name, role, route] of PAGES) {
        if (only && !only.has(name)) continue;
        const context = await browser.newContext({
          viewport,
          colorScheme: theme,
          deviceScaleFactor: 1,
        });
        if (role) {
          await context.addCookies([
            { name: "access_token", value: tokens[role].token, domain: host, path: "/" },
          ]);
        }
        await context.addInitScript(
          ([key, value]) => {
            try { window.localStorage.setItem(key, value); } catch {}
          },
          [THEME_KEY, theme],
        );
        const page = await context.newPage();
        const file = `${name}.${theme}.${form}.png`;
        const entry = { name, theme, form, route, file, ok: true };
        try {
          await page.goto(`${BASE}${route}`, { waitUntil: "networkidle", timeout: 30_000 });
          // Chờ skeleton/spinner tải dữ liệu biến mất (tối đa 8s) để ảnh có nội dung thật.
          await page
            .waitForFunction(() => !document.querySelector(".animate-pulse, .animate-spin"), null, { timeout: 8_000 })
            .catch(() => {});
          await page.waitForTimeout(400);
          await page.screenshot({ path: path.join(OUT, file), fullPage: true });
        } catch (err) {
          entry.ok = false;
          entry.error = String(err?.message || err).slice(0, 300);
        }
        index.push(entry);
        await context.close();
      }
    }
  }
} finally {
  await browser.close();
}
fs.writeFileSync(path.join(OUT, "index.json"), JSON.stringify(index, null, 2) + "\n");
const failed = index.filter((e) => !e.ok).length;
console.log(JSON.stringify({ out: OUT, shots: index.length, failed }, null, 2));
