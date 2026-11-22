#!/usr/bin/env node
/**
 * Đo capture+encode gaze phía client trong Chromium.
 *
 * So sánh đường mới (OffscreenCanvas transfer + worker encode) với đường cũ
 * (main thread drawImage + toBlob) trên cùng video, cùng 480px/q0.78:
 *   - p50/p95/max capture+encode (ms), long task >50ms trong 10s
 *   - bytes/frame, PSNR giữa JPEG cũ/mới
 *
 * Chạy: node benchmarks/frontend/gaze-capture.mjs --out <file.json>
 */

import { execFileSync } from "node:child_process";
import fs from "node:fs";
import { createServer } from "node:http";
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "../..");
const FRONTEND = path.join(ROOT, "frontend");
const require = createRequire(path.join(FRONTEND, "package.json"));
const { chromium } = require("playwright");

const args = process.argv.slice(2);
function option(name, fallback) {
  const index = args.indexOf(name);
  return index >= 0 && args[index + 1] ? args[index + 1] : fallback;
}
const outFile = path.resolve(option("--out", "gaze-capture.json"));
const frames = Number(option("--frames", "150"));
const fps = Number(option("--fps", "15"));

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "gaze-capture-"));
const tsc = path.join(FRONTEND, "node_modules", ".bin", "tsc");

execFileSync(
  tsc,
  [
    "lib/gaze/capture.ts",
    "--outDir",
    tmp,
    "--module",
    "es2022",
    "--target",
    "es2022",
    "--lib",
    "es2022,dom",
    "--skipLibCheck",
  ],
  { cwd: FRONTEND, stdio: "inherit" },
);
fs.copyFileSync(
  path.join(FRONTEND, "lib", "gaze", "capture.worker.js"),
  path.join(tmp, "capture.worker.js"),
);

const html = `<!doctype html>
<meta charset="utf-8" />
<style>html,body{margin:0}video{width:320px;height:240px}</style>
<video id="video" autoplay muted playsinline></video>
<script type="module">
import { createFrameCapturer } from "/capture.js";

const video = document.getElementById("video");
const MAX_WIDTH = 480;
const QUALITY = 0.78;

function createLegacyCapturer() {
  let canvas = null;
  return {
    dispose() {
      if (canvas) {
        canvas.width = 0;
        canvas.height = 0;
        canvas = null;
      }
    },
    async capture() {
      if (video.videoWidth === 0 || video.videoHeight === 0) return null;
      const scale = Math.min(1, MAX_WIDTH / video.videoWidth);
      const width = Math.round(video.videoWidth * scale);
      const height = Math.round(video.videoHeight * scale);
      if (!canvas) canvas = document.createElement("canvas");
      if (canvas.width !== width) canvas.width = width;
      if (canvas.height !== height) canvas.height = height;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(video, 0, 0, width, height);
      return new Promise((resolve) =>
        canvas.toBlob(resolve, "image/jpeg", QUALITY),
      );
    },
  };
}

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

window.__prepare = async () => {
  const stream = await navigator.mediaDevices.getUserMedia({
    video: { width: { ideal: 640 }, height: { ideal: 480 } },
  });
  video.srcObject = stream;
  await video.play();
  const started = performance.now();
  while (video.videoWidth === 0 && performance.now() - started < 5000) {
    await wait(50);
  }
  await wait(500);
  return { width: video.videoWidth, height: video.videoHeight };
};

async function run(capturer) {
  const times = [];
  const sizes = [];
  const interval = 1000 / ${fps};
  let next = performance.now();
  for (let index = 0; index < ${frames}; index += 1) {
    next += interval;
    const delay = next - performance.now();
    if (delay > 0) await wait(delay);
    const started = performance.now();
    const blob = await capturer.capture(video);
    times.push(performance.now() - started);
    sizes.push(blob ? blob.size : 0);
  }
  return { times, sizes };
}

window.__bench = async () => {
  const longTasks = [];
  const observer = new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) longTasks.push(entry.duration);
  });
  observer.observe({ entryTypes: ["longtask"] });

  const worker = createFrameCapturer({
    workerUrl: "./capture.worker.js",
    onFallback: (reason) => {
      window.__gazeFallback = String(reason);
    },
  });
  const legacy = createLegacyCapturer();
  const workerRun = await run(worker);
  const usingWorker = worker.usingWorker;
  const fallback = window.__gazeFallback ?? null;
  const legacyRun = await run(legacy);
  worker.dispose();
  legacy.dispose();
  observer.disconnect();
  return {
    usingWorker,
    fallback,
    worker: workerRun,
    legacy: legacyRun,
    longTasks,
  };
};

async function pixels(blob) {
  const bitmap = await createImageBitmap(blob);
  const width = bitmap.width;
  const height = bitmap.height;
  const canvas = new OffscreenCanvas(width, height);
  const ctx = canvas.getContext("2d");
  ctx.drawImage(bitmap, 0, 0);
  bitmap.close();
  return ctx.getImageData(0, 0, width, height).data;
}

window.__psnrPair = async () => {
  const worker = createFrameCapturer({ workerUrl: "./capture.worker.js" });
  const legacy = createLegacyCapturer();
  try {
    let best = null;
    for (let attempt = 0; attempt < 3; attempt += 1) {
      const pair = await new Promise((resolve) => {
        video.requestVideoFrameCallback(async () => {
          const fresh = await worker.capture(video);
          const old = await legacy.capture(video);
          resolve([fresh, old]);
        });
      });
      if (!pair[0] || !pair[1]) continue;
      const a = await pixels(pair[0]);
      const b = await pixels(pair[1]);
      if (a.length !== b.length) continue;
      let sum = 0;
      for (let index = 0; index < a.length; index += 1) {
        const diff = a[index] - b[index];
        sum += diff * diff;
      }
      const mse = sum / a.length;
      const psnr = mse === 0 ? 99 : 10 * Math.log10((255 * 255) / mse);
      if (best === null || psnr > best) best = psnr;
    }
    return best;
  } finally {
    worker.dispose();
    legacy.dispose();
  }
};
</script>`;

fs.writeFileSync(path.join(tmp, "index.html"), html, "utf8");

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
};
const server = createServer((request, response) => {
  const name = request.url === "/" ? "index.html" : request.url.slice(1);
  const file = path.join(tmp, name);
  if (!file.startsWith(tmp) || !fs.existsSync(file)) {
    response.writeHead(404).end("not found");
    return;
  }
  response.writeHead(200, {
    "content-type": MIME[path.extname(file)] ?? "application/octet-stream",
  });
  fs.createReadStream(file).pipe(response);
});

function percentile(values, q) {
  if (values.length === 0) return null;
  const ordered = [...values].sort((a, b) => a - b);
  return ordered[Math.min(ordered.length - 1, Math.floor(ordered.length * q))];
}

function round(value, digits = 3) {
  return value === null ? null : Number(value.toFixed(digits));
}

function stats(values) {
  return {
    p50: round(percentile(values, 0.5)),
    p95: round(percentile(values, 0.95)),
    max: round(Math.max(...values)),
  };
}

let browser = null;
let result;
try {
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address();
  const origin = `http://127.0.0.1:${port}`;

  browser = await chromium.launch({
    headless: true,
    args: [
      "--use-fake-device-for-media-stream",
      "--use-fake-ui-for-media-stream",
    ],
  });
  const context = await browser.newContext();
  await context.grantPermissions(["camera"], { origin });
  const page = await context.newPage();
  await page.goto(origin);
  const source = await page.evaluate(() => window.__prepare());
  const bench = await page.evaluate(() => window.__bench());
  const psnr = await page.evaluate(() => window.__psnrPair());

  const longTasks = bench.longTasks.filter((duration) => duration > 50);

  result = {
    source,
    frames,
    fps,
    usingWorker: bench.usingWorker,
    fallback: bench.fallback,
    worker: {
      ...stats(bench.worker.times),
      bytes_p50: percentile(bench.worker.sizes, 0.5),
      bytes_p95: percentile(bench.worker.sizes, 0.95),
    },
    legacy: {
      ...stats(bench.legacy.times),
      bytes_p50: percentile(bench.legacy.sizes, 0.5),
      bytes_p95: percentile(bench.legacy.sizes, 0.95),
    },
    long_tasks_over_50ms: longTasks,
    psnr_db: psnr === null ? null : round(psnr, 2),
    gates: {
      worker_p95_ms: 10,
      long_tasks: 0,
      bytes_p95: 25 * 1024,
      psnr_db: 45,
    },
  };
  result.pass =
    result.usingWorker &&
    result.fallback === null &&
    result.worker.p95 !== null &&
    result.worker.p95 <= 10 &&
    longTasks.length === 0 &&
    result.worker.bytes_p95 <= 25 * 1024 &&
    (result.psnr_db === null || result.psnr_db >= 45);
} finally {
  if (browser) await browser.close();
  server.close();
  fs.rmSync(tmp, { recursive: true, force: true });
}

fs.mkdirSync(path.dirname(outFile), { recursive: true });
fs.writeFileSync(outFile, JSON.stringify(result, null, 2) + "\n");

console.log(
  `worker  p50/p95/max ${result.worker.p50}/${result.worker.p95}/${result.worker.max} ms, ` +
    `bytes p95 ${Math.round(result.worker.bytes_p95)}`,
);
console.log(
  `legacy  p50/p95/max ${result.legacy.p50}/${result.legacy.p95}/${result.legacy.max} ms, ` +
    `bytes p95 ${Math.round(result.legacy.bytes_p95)}`,
);
console.log(
  `long task >50ms: ${result.long_tasks_over_50ms.length}; PSNR ${result.psnr_db} dB; ` +
    `gate ${result.pass ? "PASS" : "FAIL"} -> ${outFile}`,
);
process.exit(result.pass ? 0 : 1);
