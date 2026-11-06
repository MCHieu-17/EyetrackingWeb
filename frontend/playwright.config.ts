import { defineConfig, devices } from "@playwright/test";

// E2E phải chạy với backend test riêng, KHÔNG mặc định gọi backend development
// (cổng 8001). Xem docs/refactor/test-isolation.md.
const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:3012";
const apiURL = process.env.E2E_API_URL ?? "http://localhost:8011";
const gazeURL = process.env.E2E_GAZE_URL ?? "http://localhost:8010";

export default defineConfig({
  testDir: "./e2e",
  testIgnore: ["**/demo.spec.ts"],
  fullyParallel: false,
  forbidOnly: false,
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  timeout: 30_000,
  use: {
    baseURL,
    trace: "off",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: `npx next dev --port ${new URL(baseURL).port || "3012"}`,
    url: `${baseURL}/account/login`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      NEXT_PUBLIC_API_URL: apiURL,
      NEXT_PUBLIC_GAZE_URL: gazeURL,
      NEXT_PUBLIC_DEMO: "0",
    },
  },
});
