#!/usr/bin/env node
// Tổng hợp Lighthouse JSON: median 3 lần cho mobile/desktop.
import fs from 'node:fs';
import path from 'node:path';

function arg(name, fallback = '') {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 ? process.argv[i + 1] : fallback;
}

const dir = path.resolve(arg('dir'));
const out = path.resolve(arg('out', path.join(dir, 'summary.json')));
const md = path.resolve(arg('md', out.replace(/\.json$/, '.md')));

const files = fs.readdirSync(dir).filter((name) => name.endsWith('.json')).sort();
const groups = new Map();

function median(values) {
  const sorted = values.filter((v) => Number.isFinite(v)).sort((a, b) => a - b);
  if (!sorted.length) return null;
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

for (const file of files) {
  const match = /^(.*)\.(mobile|desktop)\.(\d+)\.json$/.exec(file);
  if (!match) continue;
  const [, page, form] = match;
  const data = JSON.parse(fs.readFileSync(path.join(dir, file), 'utf8'));
  const audits = data.audits || {};
  const metrics = {
    score: data.categories?.performance?.score ?? null,
    a11y: data.categories?.accessibility?.score ?? null,
    bestPractices: data.categories?.['best-practices']?.score ?? null,
    lcp: audits['largest-contentful-paint']?.numericValue ?? null,
    tbt: audits['total-blocking-time']?.numericValue ?? null,
    ttfb: audits['server-response-time']?.numericValue ?? null,
    fcp: audits['first-contentful-paint']?.numericValue ?? null,
    cls: audits['cumulative-layout-shift']?.numericValue ?? null,
    speedIndex: audits['speed-index']?.numericValue ?? null,
    interactive: audits['interactive']?.numericValue ?? null,
  };
  const key = `${page}|${form}`;
  const list = groups.get(key) || [];
  list.push(metrics);
  groups.set(key, list);
}

const summary = {};
for (const [key, list] of [...groups.entries()].sort()) {
  const [page, form] = key.split('|');
  summary[key] = {
    page,
    form,
    runs: list.length,
    score: median(list.map((m) => m.score)),
    a11y: median(list.map((m) => m.a11y)),
    bestPractices: median(list.map((m) => m.bestPractices)),
    lcp: median(list.map((m) => m.lcp)),
    tbt: median(list.map((m) => m.tbt)),
    ttfb: median(list.map((m) => m.ttfb)),
    fcp: median(list.map((m) => m.fcp)),
    cls: median(list.map((m) => m.cls)),
    speedIndex: median(list.map((m) => m.speedIndex)),
    interactive: median(list.map((m) => m.interactive)),
  };
}

fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, JSON.stringify(summary, null, 2) + '\n');

const lines = [
  '# Lighthouse summary (median)',
  '',
  '| Page | Form | Perf | A11y | Best pr. | LCP ms | TBT ms | TTFB ms | CLS |',
  '|---|---|---:|---:|---:|---:|---:|---:|---:|',
];
for (const item of Object.values(summary)) {
  const fmt = (v, digits = 1) => (v == null ? '-' : Number(v).toFixed(digits));
  lines.push(`| ${item.page} | ${item.form} | ${fmt(item.score, 2)} | ${fmt(item.a11y, 2)} | ${fmt(item.bestPractices, 2)} | ${fmt(item.lcp)} | ${fmt(item.tbt)} | ${fmt(item.ttfb)} | ${fmt(item.cls, 3)} |`);
}
fs.writeFileSync(md, lines.join('\n') + '\n');
console.log(JSON.stringify({ out, md, groups: Object.keys(summary).length }, null, 2));
