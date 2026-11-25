import fs from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { fixtures, storageStateFor } from "./support/fixtures";

/**
 * Hợp đồng AOI giao diện (ui_schema reader-v1).
 *
 * Gaze được map vào rect của `[data-aoi]` (lib/aoi/measure.ts) và anchor AOI
 * lưu toạ độ tương đối trong box của anchor. Vì vậy redesign chỉ được đổi
 * màu ở reader/quiz/chat: tập code và hình học phải giữ nguyên.
 *
 * Golden: e2e/aoi-geometry.golden.json. Ghi lại có chủ đích bằng
 *   UPDATE_AOI_GOLDEN=1 ./scripts/e2e.sh aoi-contract
 */

const GOLDEN = path.join(__dirname, "aoi-geometry.golden.json");
const TOLERANCE = 0.005;
const VIEWPORT = { width: 1440, height: 900 };

type Rect = { code: string; xMin: number; yMin: number; xMax: number; yMax: number };

async function measure(page: Page): Promise<Rect[]> {
  return page.evaluate(() => {
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const out: Rect[] = [];
    document.querySelectorAll<HTMLElement>("[data-aoi]").forEach((el) => {
      const code = el.dataset.aoi?.trim();
      if (!code) return;
      const r = el.getBoundingClientRect();
      if (r.width <= 0 || r.height <= 0) return;
      out.push({
        code,
        xMin: Math.max(0, r.left / vw),
        yMin: Math.max(0, r.top / vh),
        xMax: Math.min(1, r.right / vw),
        yMax: Math.min(1, r.bottom / vh),
      });
    });
    return out.sort((a, b) => a.code.localeCompare(b.code) || a.yMin - b.yMin || a.xMin - b.xMin);
  });
}

async function codesOutsideRoot(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const root = document.querySelector('[data-aoi="reader-root"]');
    return [...document.querySelectorAll<HTMLElement>("[data-aoi]")]
      .filter((el) => el !== root && !root?.contains(el))
      .map((el) => el.dataset.aoi ?? "");
  });
}

function compareGolden(state: string, rects: Rect[]) {
  const update = process.env.UPDATE_AOI_GOLDEN === "1";
  const golden: Record<string, Rect[]> = fs.existsSync(GOLDEN)
    ? JSON.parse(fs.readFileSync(GOLDEN, "utf8"))
    : {};
  if (update || !golden[state]) {
    golden[state] = rects.map((r) => ({
      code: r.code,
      xMin: +r.xMin.toFixed(4),
      yMin: +r.yMin.toFixed(4),
      xMax: +r.xMax.toFixed(4),
      yMax: +r.yMax.toFixed(4),
    }));
    fs.writeFileSync(GOLDEN, JSON.stringify(golden, null, 2) + "\n");
    return;
  }
  const expected = golden[state];
  expect(rects.map((r) => r.code), `${state}: tập data-aoi`).toEqual(
    expected.map((r) => r.code),
  );
  rects.forEach((r, i) => {
    const e = expected[i];
    for (const k of ["xMin", "yMin", "xMax", "yMax"] as const) {
      expect(
        Math.abs(r[k] - e[k]),
        `${state}: ${r.code}.${k} lệch (${r[k].toFixed(4)} vs ${e[k]})`,
      ).toBeLessThanOrEqual(TOLERANCE);
    }
  });
}

test.describe("hợp đồng data-aoi của reader", () => {
  test.use({ viewport: VIEWPORT });

  test("reader học viên: slide, quiz, chat giữ đủ code và hình học", async ({
    browser,
    request,
  }) => {
    const data = fixtures();
    const context = await browser.newContext({
      viewport: VIEWPORT,
      storageState: await storageStateFor(request, "student"),
    });
    const page = await context.newPage();
    await page.goto(`/student/courses/${data.course_id}`);
    await expect(page.getByRole("heading", { name: "Bài giảng E2E" })).toBeVisible();
    await expect(page.locator('[data-aoi="slide"]')).toBeVisible();
    await page.waitForTimeout(800);

    const slide = await measure(page);
    const slideCodes = new Set(slide.map((r) => r.code));
    for (const code of ["reader-root", "header", "chat-open-button", "outline", "lesson-content", "slide", "lesson-nav"]) {
      expect(slideCodes, `thiếu ${code}`).toContain(code);
    }
    expect(await codesOutsideRoot(page)).toEqual([]);
    compareGolden("student.slide", slide);

    await page.getByRole("button", { name: "Mở trợ lý học tập" }).click();
    await expect(page.locator('[data-aoi="chatbot"]')).toBeVisible();
    await page.waitForTimeout(600);
    const chat = await measure(page);
    const chatCodes = new Set(chat.map((r) => r.code));
    for (const code of ["chatbot", "chat-header", "chat-messages", "chat-input", "chat-send"]) {
      expect(chatCodes, `thiếu ${code}`).toContain(code);
    }
    expect(await codesOutsideRoot(page)).toEqual([]);
    compareGolden("student.chat", chat);
    await page.getByRole("button", { name: "Đóng trợ lý học tập" }).click();

    await page.getByRole("button", { name: /Bài tập E2E/ }).click();
    const retry = page.getByRole("button", { name: "Làm lại", exact: true });
    // Chờ quiz tải xong (câu hỏi đang làm HOẶC màn kết quả) rồi mới quyết định.
    await expect(
      page.getByRole("button", { name: "Nộp bài" }).or(retry),
    ).toBeVisible();
    if (await retry.isVisible()) {
      await retry.click();
      await page
        .getByRole("dialog")
        .getByRole("button", { name: "Làm lại", exact: true })
        .click();
    }
    await expect(page.getByText("1 + 1 bằng mấy?")).toBeVisible();
    await page.waitForTimeout(600);
    const quiz = await measure(page);
    const quizCodes = new Set(quiz.map((r) => r.code));
    for (const code of ["quiz", "quiz-question", "quiz-options", "quiz-submit"]) {
      expect(quizCodes, `thiếu ${code}`).toContain(code);
    }
    compareGolden("student.quiz", quiz);
    await context.close();
  });

  test("bản xem trước của giáo viên dùng cùng tập code", async ({
    browser,
    request,
  }) => {
    const data = fixtures();
    const context = await browser.newContext({
      viewport: VIEWPORT,
      storageState: await storageStateFor(request, "teacher"),
    });
    const page = await context.newPage();
    await page.goto(`/teacher/courses/${data.course_id}?tab=aoi`);
    await expect(page.locator('[data-aoi="reader-root"]')).toBeVisible();
    await page.waitForTimeout(800);
    const codes = new Set((await measure(page)).map((r) => r.code));
    for (const code of ["reader-root", "header", "outline", "lesson-content", "slide", "lesson-nav"]) {
      expect(codes, `preview thiếu ${code}`).toContain(code);
    }
    await context.close();
  });
});
