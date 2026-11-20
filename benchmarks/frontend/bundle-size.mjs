#!/usr/bin/env node
// Đo bundle production từ .next/server/app/**/page_client-reference-manifest.js.
//
//   node benchmarks/frontend/bundle-size.mjs \
//     --next-dir benchmarks/baseline/<run>/frontend/.next \
//     --out .../frontend/bundle-size.json \
//     --md .../frontend/bundle-size.md

import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import zlib from 'node:zlib';
import { fileURLToPath } from 'node:url';

function arg(name, fallback = '') {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 ? process.argv[i + 1] : fallback;
}

const nextDir = path.resolve(arg('next-dir', 'frontend/.next'));
const out = path.resolve(arg('out', 'benchmarks/baseline/bundle-size.json'));
const md = path.resolve(arg('md', out.replace(/\.json$/, '.md')));

function walk(dir, outList = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, outList);
    else if (entry.name.endsWith('page_client-reference-manifest.js')) outList.push(full);
  }
  return outList;
}

function routeOf(file) {
  const rel = path.relative(path.join(nextDir, 'server/app'), file).replaceAll(path.sep, '/');
  let route = rel
    .replace(/page_client-reference-manifest\.js$/, '')
    .replace(/\/page$/, '')
    .replace(/\/$/, '');
  if (!route) route = '';
  return '/' + route;
}

function sizeOf(rel) {
  const file = path.join(nextDir, rel);
  if (!fs.existsSync(file)) return null;
  const raw = fs.statSync(file).size;
  const buffer = fs.readFileSync(file);
  return {
    raw,
    gzip: zlib.gzipSync(buffer, { level: 9 }).length,
  };
}

const files = walk(path.join(nextDir, 'server/app'));
const routes = {};
const chunkTotals = new Map();

for (const file of files) {
  const code = fs.readFileSync(file, 'utf8');
  const sandbox = {};
  vm.createContext(sandbox);
  vm.runInContext(code, sandbox, { filename: file });
  const manifest = sandbox.__RSC_MANIFEST || {};
  const entry = Object.values(manifest)[0];
  if (!entry) continue;

  const js = new Set();
  const css = new Set();
  for (const chunks of Object.values(entry.entryJSFiles || {})) {
    for (const chunk of chunks || []) {
      const rel = chunk.replace(/^\//, '');
      if (rel.endsWith('.css')) css.add(rel);
      else js.add(rel);
    }
  }
  for (const chunks of Object.values(entry.entryCSSFiles || {})) {
    for (const chunk of chunks || []) {
      const rel = String(typeof chunk === 'string' ? chunk : chunk.path || '').replace(/^\//, '');
      if (rel.endsWith('.css')) css.add(rel);
    }
  }
  for (const info of Object.values(entry.clientModules || {})) {
    for (const chunk of info.chunks || []) {
      const rel = chunk.replace(/^\//, '');
      if (rel.endsWith('.css')) css.add(rel);
    }
  }

  let jsRaw = 0;
  let jsGzip = 0;
  let cssRaw = 0;
  let cssGzip = 0;
  for (const rel of js) {
    const size = sizeOf(rel);
    if (!size) continue;
    jsRaw += size.raw;
    jsGzip += size.gzip;
    const prev = chunkTotals.get(rel) || { raw: 0, gzip: 0 };
    chunkTotals.set(rel, { raw: Math.max(prev.raw, size.raw), gzip: Math.max(prev.gzip, size.gzip) });
  }
  for (const rel of css) {
    const size = sizeOf(rel);
    if (!size) continue;
    cssRaw += size.raw;
    cssGzip += size.gzip;
    const prev = chunkTotals.get(rel) || { raw: 0, gzip: 0 };
    chunkTotals.set(rel, { raw: Math.max(prev.raw, size.raw), gzip: Math.max(prev.gzip, size.gzip) });
  }
  routes[routeOf(file)] = {
    jsFiles: [...js].sort(),
    cssFiles: [...css].sort(),
    jsRaw,
    jsGzip,
    cssRaw,
    cssGzip,
  };
}

const staticDir = path.join(nextDir, 'static');
let staticRaw = 0;
let staticGzip = 0;
let staticFiles = 0;
if (fs.existsSync(staticDir)) {
  const stack = [staticDir];
  while (stack.length) {
    const dir = stack.pop();
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) stack.push(full);
      else {
        staticFiles += 1;
        const buffer = fs.readFileSync(full);
        staticRaw += buffer.length;
        staticGzip += zlib.gzipSync(buffer, { level: 9 }).length;
      }
    }
  }
}

const topChunks = [...chunkTotals.entries()]
  .map(([file, size]) => ({ file, ...size }))
  .sort((a, b) => b.raw - a.raw)
  .slice(0, 30);

const result = {
  nextDir,
  generatedAt: new Date().toISOString(),
  static: { files: staticFiles, raw: staticRaw, gzip: staticGzip },
  routes,
  topChunks,
};

fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, JSON.stringify(result, null, 2) + '\n');

const lines = [
  '# Frontend bundle size',
  '',
  `- Next dir: \`${nextDir}\``,
  `- Static files: ${staticFiles}`,
  `- Static raw: ${staticRaw} bytes (${(staticRaw / 1024).toFixed(1)} KiB)`,
  `- Static gzip: ${staticGzip} bytes (${(staticGzip / 1024).toFixed(1)} KiB)`,
  '',
  '| Route | JS raw KiB | JS gzip KiB | CSS raw KiB | CSS gzip KiB |',
  '|---|---:|---:|---:|---:|',
];
for (const [route, value] of Object.entries(routes).sort()) {
  lines.push(
    `| ${route} | ${(value.jsRaw / 1024).toFixed(1)} | ${(value.jsGzip / 1024).toFixed(1)} | ` +
    `${(value.cssRaw / 1024).toFixed(1)} | ${(value.cssGzip / 1024).toFixed(1)} |`,
  );
}
lines.push('', '## Top chunks', '', '| File | Raw KiB | Gzip KiB |', '|---|---:|---:|');
for (const item of topChunks) {
  lines.push(`| ${item.file} | ${(item.raw / 1024).toFixed(1)} | ${(item.gzip / 1024).toFixed(1)} |`);
}
fs.writeFileSync(md, lines.join('\n') + '\n');
console.log(JSON.stringify({ out, md, routes: Object.keys(routes).length }, null, 2));
