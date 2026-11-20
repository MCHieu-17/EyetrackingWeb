// Gửi gaze batch vào backend. Mỗi VU dùng một student token + session/view
// riêng trong fixtures.gaze_targets để tránh tranh unique/rate-limit.
//
//   k6 run -e BASE_URL=http://127.0.0.1:8101 \
//     -e TOKEN_FILE=... -e FIXTURES=... -e SAMPLES=40 -e VUS=25 -e DURATION=30s \
//     benchmarks/backend/k6/gaze_batch.js

import http from 'k6/http';
import { check, sleep } from 'k6';

function randomUUID() {
  const hex = '0123456789abcdef';
  let out = '';
  for (let i = 0; i < 36; i += 1) {
    if (i === 8 || i === 13 || i === 18 || i === 23) out += '-';
    else if (i === 14) out += '4';
    else if (i === 19) out += hex[(Math.floor(Math.random() * 4) + 8)];
    else out += hex[Math.floor(Math.random() * 16)];
  }
  return out;
}

const BASE = (__ENV.BASE_URL || 'http://127.0.0.1:8101').replace(/\/$/, '');
const tokens = JSON.parse(open(__ENV.TOKEN_FILE));
const fixtures = JSON.parse(open(__ENV.FIXTURES));
const targets = fixtures.gaze_targets || [];
const samples = Math.max(1, Math.min(2000, Number(__ENV.SAMPLES || 40)));
const vus = Number(__ENV.VUS || Math.min(25, targets.length));
const duration = __ENV.DURATION || '30s';
const batchPerSecond = Number(__ENV.BATCH_PER_SECOND || 1);

export const options = {
  vus,
  duration,
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'],
};

let sequence = 0;

function isoNow(offsetMs) {
  return new Date(Date.now() + offsetMs).toISOString();
}

export default function () {
  if (!targets.length) throw new Error('fixtures.gaze_targets empty');
  const target = targets[(__VU - 1) % targets.length];
  const student = tokens.students[target.token_index % tokens.students.length];
  const start = sequence;
  const end = sequence + samples - 1;
  const body = {
    batchId: randomUUID(),
    presentationId: target.presentation_id,
    layoutId: target.layout_id,
    sequenceStart: start,
    sequenceEnd: end,
    samples: Array.from({ length: samples }, (_, i) => ({
      sequence: start + i,
      eventTime: isoNow(i * 66),
      viewportX: 0.2 + ((i * 7) % 50) / 100,
      viewportY: 0.2 + ((i * 11) % 50) / 100,
      status: 'ok',
      qualityFlags: {},
    })),
  };
  sequence += samples;

  const res = http.post(
    `${BASE}/api/learning-sessions/${target.session_id}/gaze-batches`,
    JSON.stringify(body),
    {
      headers: {
        Authorization: `Bearer ${student.token}`,
        'Content-Type': 'application/json',
        'X-Request-ID': `bench-gaze-${__VU}-${__ITER}`,
      },
      tags: { endpoint: 'POST /api/learning-sessions/:id/gaze-batches' },
      timeout: '30s',
    },
  );
  check(res, {
    'gaze batch 200': (r) => r.status === 200,
    'gaze batch stored': (r) => {
      try {
        const data = r.json();
        return data.stored === samples && data.duplicate === 0;
      } catch (_) {
        return false;
      }
    },
  });
  if (batchPerSecond > 0) sleep(1 / batchPerSecond);
}

export function handleSummary(data) {
  const base = __ENV.OUT_PREFIX || '/tmp/k6-gaze';
  return {
    [`${base}.summary.json`]: JSON.stringify(data, null, 2),
    [`${base}.summary.md`]: `# gaze batch\n\nsamples=${samples} vus=${vus}\n`,
  };
}
