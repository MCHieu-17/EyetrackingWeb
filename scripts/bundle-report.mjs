#!/usr/bin/env node
// Báo cáo initial JS theo route từ Next build manifest.
//
//   node scripts/bundle-report.mjs
//
// Chạy sau `npm run build` trong frontend/. Không cần thêm dependency.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const nextDir = path.join(root, "frontend", ".next");
const appDir = path.join(nextDir, "server", "app");

const routes = [
  ["/", "page"],
  ["/student", "student/page"],
  ["/teacher", "teacher/page"],
  ["/admin", "admin/page"],
  ["/try", "try/page"],
];

function initialChunks(routeFile) {
  const file = path.join(appDir, `${routeFile}_client-reference-manifest.js`);
  if (!fs.existsSync(file)) return null;
  const source = fs.readFileSync(file, "utf8");
  const match = source.match(
    /globalThis\.__RSC_MANIFEST\["[^"]+"\]\s*=\s*(.*);\s*$/s,
  );
  if (!match) return null;
  const manifest = JSON.parse(match[1]);
  const chunks = new Set();
  for (const entry of Object.values(manifest.clientModules ?? {})) {
    for (const raw of entry.chunks ?? []) {
      const chunk = raw.replace(/^\/_next\//, "").replace(/^\//, "");
      if (chunk.startsWith("static/")) chunks.add(chunk);
    }
  }
  let bytes = 0;
  for (const chunk of chunks) {
    const filePath = path.join(nextDir, chunk);
    if (fs.existsSync(filePath)) bytes += fs.statSync(filePath).size;
  }
  return { files: chunks.size, bytes };
}

let failed = false;
console.log("route\tfiles\tinitial_js_kb");
for (const [route, routeFile] of routes) {
  const result = initialChunks(routeFile);
  if (result === null) {
    console.log(`${route}\t-\t-`);
    failed = true;
    continue;
  }
  console.log(
    `${route}\t${result.files}\t${(result.bytes / 1024).toFixed(1)}`,
  );
}

if (failed) {
  console.error(
    "\nKhông đọc được manifest. Hãy chạy `npm run build` trong frontend/ trước.",
  );
  process.exitCode = 1;
}
