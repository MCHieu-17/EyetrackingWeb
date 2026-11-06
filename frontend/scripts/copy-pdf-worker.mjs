import { cpSync, copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const pdfjsRoot = resolve(root, "node_modules/pdfjs-dist");
const source = resolve(pdfjsRoot, "build/pdf.worker.min.mjs");
const target = resolve(root, "public/pdf.worker.min.mjs");

if (!existsSync(source)) {
  // Docker deps stage chạy trước khi copy source; builder sẽ chạy lại.
  console.log("pdfjs-dist chưa được cài; bỏ qua copy PDF.js assets.");
  process.exit(0);
}

mkdirSync(dirname(target), { recursive: true });
copyFileSync(source, target);

// Font chuẩn, CMap, WASM và ICC giúp PDF.js render PDF không nhúng font
// (đặc biệt tài liệu tiếng Việt/CJK) ổn định hơn.
for (const name of ["standard_fonts", "cmaps", "wasm", "iccs"]) {
  const from = resolve(pdfjsRoot, name);
  if (!existsSync(from)) continue;
  cpSync(from, resolve(root, "public/pdfjs", name), { recursive: true });
}

console.log("Copied PDF.js worker + assets to public/");
