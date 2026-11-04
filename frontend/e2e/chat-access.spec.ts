import { test, expect } from "@playwright/test";
import { json, mockApi, seedAuth, seedCalibration } from "./fixtures";

const student = { email: "student@school.edu.vn", fullName: "Nguyễn Văn An", role: "student" as const };

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await seedAuth(page, student);
  await mockApi(page, { user: student });
  await seedCalibration(page);
});

test("polling closes the panel; a lecture change and reload retain the course lock", async ({ page }) => {
  let allowed = true;
  await page.route("**/api/courses/*/chat/access", r => json(r, {
    allowed, reason: allowed ? null : "Chatbot bị khóa trong khóa học", blockedUntil: allowed ? null : "2099-01-01T00:00:00Z",
  }));
  await page.goto("/student/courses/course-1");
  await page.getByRole("button", { name: "Mở trợ lý học tập" }).click();
  await expect(page.locator('[data-aoi="chatbot"]')).toBeVisible();
  allowed = false;
  await expect(page.locator('[data-aoi="chatbot"]')).toBeHidden({ timeout: 8000 });
  await expect(page.getByText("Trợ lý đang khóa")).toBeVisible();
  await page.getByRole("button", { name: "Bài 2: Biến" }).click();
  await page.getByRole("button", { name: "Mở trợ lý học tập" }).click();
  await expect(page.locator('[data-aoi="chatbot"]')).toHaveCount(0);
  await page.reload();
  await expect(page.getByText("Trợ lý đang khóa")).toBeVisible();
});

test("quiz chat includes all current draft selections", async ({ page }) => {
  let request: Record<string, unknown> | undefined;
  await page.route("**/api/courses/*/chat/stream", async r => {
    request = r.request().postDataJSON();
    return r.fulfill({ contentType: "text/event-stream", body: 'event: session\ndata: {"sessionId":"s"}\n\nevent: token\ndata: {"text":"Hãy đọc lại khái niệm."}\n\nevent: done\ndata: {"sessionId":"s","verified":true}\n\n' });
  });
  await page.goto("/student/courses/course-1?lesson=lesson-quiz-1");
  await page.getByText("def", { exact: true }).click();
  await page.getByRole("button", { name: "Tiếp" }).click();
  await page.getByText("list", { exact: true }).click();
  await page.getByRole("button", { name: "Mở trợ lý học tập" }).click();
  const panel = page.locator('[data-aoi="chatbot"]');
  await panel.locator("textarea").fill("Gợi ý câu tiếp theo");
  await panel.locator("textarea").press("Enter");
  await expect.poll(() => request).toBeDefined();
  expect(request?.assignmentId).toBe("quiz-python-1");
  expect(request?.draftAnswers).toEqual({ "q-1": ["q-1-b"], "q-2": ["q-2-c"] });
});

test("access lookup failure prevents opening cached chat", async ({ page }) => {
  await page.route("**/api/courses/*/chat/access", r => json(r, { detail: "offline" }, 503));
  await page.goto("/student/courses/course-1");
  await page.getByRole("button", { name: "Mở trợ lý học tập" }).click();
  await expect(page.locator('[data-aoi="chatbot"]')).toHaveCount(0);
});

test("another tab starting a restricted quiz closes chat when this tab regains focus", async ({ page, context }) => {
  let allowed = true;
  const access = { allowed: true, reason: null as string | null, blockedUntil: null };
  await page.route("**/api/courses/*/chat/access", r => json(r, { ...access, allowed, reason: allowed ? null : "Đang làm bài không cho phép chatbot" }));
  await page.goto("/student/courses/course-1");
  await page.getByRole("button", { name: "Mở trợ lý học tập" }).click();
  await expect(page.locator('[data-aoi="chatbot"]')).toBeVisible();
  const second = await context.newPage();
  await mockApi(second, { user: student });
  await seedCalibration(second);
  await second.route("**/api/courses/*/chat/access", r => json(r, { ...access, allowed, reason: allowed ? null : "Đang làm bài không cho phép chatbot" }));
  await second.goto("/student/courses/course-1?lesson=lesson-quiz-1");
  await expect(second.getByText("Câu 1 / 3")).toBeVisible();
  allowed = false;
  await page.bringToFront();
  await page.evaluate(() => document.dispatchEvent(new Event("visibilitychange")));
  await expect(page.locator('[data-aoi="chatbot"]')).toBeHidden({ timeout: 8000 });
  await expect(page.getByText("Trợ lý đang khóa")).toBeVisible();
  allowed = true; // The backend's submission/expiry transition is covered by DB tests.
  await page.getByRole("button", { name: "Mở trợ lý học tập" }).click();
  await expect(page.locator('[data-aoi="chatbot"]')).toBeVisible();
  await second.close();
});

test("one assistant bubble changes from waiting to the completed reply", async ({ page }) => {
  let release!: () => void;
  const responseReady = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/api/courses/*/chat/stream", async (route) => {
    await responseReady;
    await route.fulfill({
      contentType: "text/event-stream",
      body: 'event: session\ndata: {"sessionId":"s"}\n\nevent: status\ndata: {"stage":"generating"}\n\nevent: token\ndata: {"text":"Xin chào, mình có thể giúp bạn học bài."}\n\nevent: done\ndata: {"sessionId":"s","verified":true}\n\n',
    });
  });
  await page.route("**/api/chat/sessions/s/messages", (route) => json(route, [
    { id: "user-1", role: "student", content: "xin chào", citations: [] },
    { id: "assistant-1", role: "assistant", content: "Xin chào, mình có thể giúp bạn học bài.", citations: [] },
  ]));
  await page.goto("/student/courses/course-1");
  await page.getByRole("button", { name: "Mở trợ lý học tập" }).click();
  const panel = page.locator('[data-aoi="chatbot"]');
  await panel.locator("textarea").fill("xin chào");
  await panel.locator("textarea").press("Enter");
  try {
    await expect(panel.locator('[data-aoi="chat-ai-message"]')).toHaveCount(1);
    await expect(panel.locator('[data-aoi="chat-ai-message"]')).toContainText("Đang phân loại câu hỏi");
  } finally {
    release();
  }
  await expect(panel.locator('[data-aoi="chat-ai-message"]')).toContainText("Xin chào, mình có thể giúp bạn học bài.");
  await expect(panel.locator('[data-aoi="chat-ai-message"]')).toHaveCount(1);
  await expect(panel.locator("textarea")).toBeEnabled();
});

test("three questions continue one course session with complete math and tables", async ({ page }) => {
  const requests: Record<string, unknown>[] = [];
  const history: Record<string, unknown>[] = [];
  await page.route("**/api/chat/sessions/stable/messages", r => json(r, history));
  await page.route("**/api/courses/*/chat/stream", async r => {
    const body = r.request().postDataJSON();
    requests.push(body);
    const answer = `Câu trả lời ${requests.length}\n\n$\\frac{1}{2}$\n\n| A | B |\n|---|---|\n| 1 | 2 |`;
    history.push({ id: `u${requests.length}`, role: "student", content: body.message, citations: [] }, { id: `a${requests.length}`, role: "assistant", content: answer, citations: [] });
    await r.fulfill({ contentType: "text/event-stream", body: `event: session\ndata: {"sessionId":"stable"}\n\nevent: token\ndata: ${JSON.stringify({text: answer})}\n\nevent: done\ndata: {"sessionId":"stable","verified":true}\n\n` });
  });
  await page.goto("/student/courses/course-1");
  await page.getByRole("button", { name: "Mở trợ lý học tập" }).click();
  const panel = page.locator('[data-aoi="chatbot"]');
  for (let i = 1; i <= 3; i++) {
    if (i === 3) await page.getByRole("button", { name: "Bài 2: Biến" }).click();
    await panel.locator("textarea").fill(`Câu hỏi ${i}`);
    await panel.locator("textarea").press("Enter");
    await expect(panel.locator('[data-aoi="chat-ai-message"]')).toHaveCount(i);
    await expect(panel.locator("textarea")).toBeEnabled();
    await expect(panel.locator("table")).toHaveCount(i);
  }
  expect(requests[0].sessionId).toBeNull();
  expect(requests.slice(1).map(r => r.sessionId)).toEqual(["stable", "stable"]);
  await expect(panel.locator(".katex")).toHaveCount(3);
  await expect(panel.getByText("Câu hỏi 1", { exact: true })).toBeVisible();
  await expect(panel.locator("textarea")).toHaveAttribute("placeholder", "Nhập câu hỏi…");
});

test("chat panel fits desktop widths and restores history after reload", async ({ page }) => {
  await page.route("**/api/courses/*/chat/sessions", r => json(r, [{ id: "saved", title: "Đã lưu", canContinue: true, messageCount: 2 }]));
  await page.route("**/api/chat/sessions/saved/messages", r => json(r, [{id: "a", role: "assistant", content: "Hội thoại đã lưu", citations: []}]));
  await page.goto("/student/courses/course-1");
  await page.getByRole("button", {name: "Mở trợ lý học tập"}).click();
  const panel = page.locator('[data-aoi="chatbot"]');
  for (const width of [1280, 1366, 1440, 1920]) {
    await page.setViewportSize({width, height: 1080});
    await expect(panel).toBeVisible();
    const box = await panel.boundingBox();
    expect(box!.width).toBeGreaterThanOrEqual(360);
    expect(box!.width).toBeLessThanOrEqual(480);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  await page.reload();
  await page.getByRole("button", {name: "Mở trợ lý học tập"}).click();
  await expect(panel.getByText("Hội thoại đã lưu")).toBeVisible();
});

test("approved block is visible before the stream finishes", async ({ page }) => {
  await page.addInitScript(() => {
    const original = window.fetch.bind(window);
    window.fetch = async (input, init) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (!url.includes("/chat/stream")) return original(input, init);
      const encoder = new TextEncoder();
      return new Response(new ReadableStream({ start(controller) {
        const send = (event: string, data: unknown) => controller.enqueue(encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`));
        send("session", { sessionId: "stream-test" });
        send("token", { text: "Đoạn đã kiểm chứng.\n\n$x^2$\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n```python\nprint(1)\n```", route: "knowledge", block_id: 0 });
        (window as Window & { finishChat?: () => void }).finishChat = () => {
          send("token", { text: "\n\nĐoạn tiếp theo.", block_id: 1 });
          send("done", { sessionId: "stream-test", verified: true });
          controller.close();
        };
      }}), { headers: { "Content-Type": "text/event-stream" } });
    };
  });
  await page.goto("/student/courses/course-1");
  await page.getByRole("button", { name: "Mở trợ lý học tập" }).click();
  const panel = page.locator('[data-aoi="chatbot"]');
  await panel.locator("textarea").fill("Giải thích nội dung");
  await panel.locator("textarea").press("Enter");
  await expect(panel).toContainText("Đoạn đã kiểm chứng.");
  await expect(panel.locator(".katex")).toBeVisible();
  await expect(panel.locator("table")).toBeVisible();
  await expect(panel.locator("pre code")).toContainText("print(1)");
  await expect(panel).not.toContainText("Đoạn tiếp theo.");
  await page.evaluate(() => (window as Window & { finishChat?: () => void }).finishChat?.());
  await expect(panel).toContainText("Đoạn tiếp theo.");
});
