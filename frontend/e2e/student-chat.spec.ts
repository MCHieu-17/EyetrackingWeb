import { expect, test } from "@playwright/test";
import { fixtures, login } from "./support/fixtures";

const enabled = process.env.E2E_CHAT === "1";

test.describe("trợ lý học tập", () => {
  test.skip(!enabled, "Đặt E2E_CHAT=1 và chạy stack chatbot/LLM thật");

  test("student mở chat, nhận token và citation", async ({ page }) => {
    const data = fixtures();
    await login(page, "student@school.edu.vn");
    await expect(page).toHaveURL(/\/student/);
    await page.getByText(data.title, { exact: true }).first().click();

    await page
      .getByRole("button", { name: "Mở trợ lý học tập" })
      .click();
    await expect(
      page.getByRole("dialog", { name: "Trợ lý học tập" }),
    ).toBeVisible();

    const input = page.getByLabel("Câu hỏi cho trợ lý");
    await input.fill("alpha là gì?");
    await page.getByRole("button", { name: "Gửi câu hỏi" }).click();

    await expect(
      page.getByRole("button", { name: /Xem nguồn trích dẫn/ }).first(),
    ).toBeVisible({ timeout: 60_000 });
  });
});
