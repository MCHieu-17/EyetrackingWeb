// k6 scenario cho các endpoint backend chính.
//
// Chạy:
//   k6 run -e BASE_URL=http://127.0.0.1:8101 \
//     -e TOKEN_FILE=/bench/.../.runtime/tokens.json \
//     -e FIXTURES=/bench/.../fixtures.json \
//     -e SCENARIO=teacher_courses \
//     --summary-export /bench/.../backend/k6/teacher_courses.json \
//     benchmarks/backend/k6/api.js
//
// Không đặt threshold cứng trong baseline: mục tiêu là ghi nhận, không phải
// làm đỏ CI. Sau khi có baseline mới chốt SLO.

import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = (__ENV.BASE_URL || 'http://127.0.0.1:8101').replace(/\/$/, '');
const scenario = __ENV.SCENARIO || 'enrollments';
const vus = Number(__ENV.VUS || 10);
const iterations = Number(__ENV.ITERATIONS || 0);
const duration = __ENV.DURATION || '30s';
const thinkTime = Number(__ENV.THINK_TIME || 0.2);

const tokens = JSON.parse(open(__ENV.TOKEN_FILE));
const fixtures = JSON.parse(open(__ENV.FIXTURES));
const ids = fixtures.ids;

const summaryTrendStats = ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'];

export const options = iterations > 0
  ? { vus, iterations, summaryTrendStats }
  : { vus, duration, summaryTrendStats };

function headers(token, json = false) {
  const h = { Authorization: `Bearer ${token}`, 'X-Request-ID': `bench-${__VU}-${__ITER}` };
  if (json) h['Content-Type'] = 'application/json';
  return h;
}

function studentToken() {
  const list = tokens.students || [];
  return (list[(__VU - 1) % Math.max(1, list.length)] || tokens.student).token;
}

function call(path, opts, name, expected = [200]) {
  const res = http.request(opts.method || 'GET', `${BASE}${path}`, opts.body || null, {
    headers: opts.headers,
    tags: { endpoint: name, scenario },
    timeout: opts.timeout || '60s',
  });
  check(res, {
    [`${name} status`]: (r) => expected.includes(r.status),
  });
}

function post(path, token, body, name, expected = [200]) {
  call(path, {
    method: 'POST',
    headers: headers(token, true),
    body: JSON.stringify(body || {}),
  }, name, expected);
}

function get(path, token, name, expected = [200]) {
  call(path, { method: 'GET', headers: headers(token) }, name, expected);
}

export default function () {
  const teacher = tokens.teacher.token;
  const student = studentToken();
  const core = ids.core_course_id;
  const visit = ids.core_visit_id;
  const view = (ids.core_view_ids || [])[0];
  const target = (fixtures.gaze_targets || [])[((__VU - 1) % Math.max(1, (fixtures.gaze_targets || []).length))];
  const session = target?.session_id;

  switch (scenario) {
    case 'enrollments':
      get('/api/me/enrollments', student, 'GET /api/me/enrollments');
      break;
    case 'me':
      get('/api/me/profile', student, 'GET /api/me/profile');
      break;
    case 'outline':
      get(`/api/courses/${core}`, student, 'GET /api/courses/:id');
      break;
    case 'lesson_contents':
      get(`/api/lessons/${ids.core_lesson_ids[0]}/contents`, student,
        'GET /api/lessons/:id/contents');
      break;
    case 'session_contents':
      if (!session) throw new Error('fixtures.gaze_targets[0].session_id missing');
      get(`/api/learning-sessions/${session}/contents`, student,
        'GET /api/learning-sessions/:id/contents');
      break;
    case 'teacher_courses':
      get('/teacher/courses?limit=200', teacher, 'GET /teacher/courses');
      break;
    case 'teacher_tree':
      get(`/teacher/courses/${core}`, teacher, 'GET /teacher/courses/:id');
      break;
    case 'course_students':
      get(`/teacher/courses/${core}/students`, teacher,
        'GET /teacher/courses/:id/students');
      break;
    case 'add_students':
      post(`/teacher/courses/${ids.draft_course_id}/students`, teacher,
        { studentIds: fixtures.student_ids || [] },
        'POST /teacher/courses/:id/students', [201]);
      break;
    case 'course_visits':
      get(`/teacher/courses/${core}/visits?limit=200&includeShort=true`, teacher,
        'GET /teacher/courses/:id/visits');
      break;
    case 'visit_summary':
      get(`/teacher/visits/${visit}/summary`, teacher,
        'GET /teacher/visits/:id/summary');
      break;
    case 'replay':
      get(`/teacher/visits/${visit}/replay`, teacher,
        'GET /teacher/visits/:id/replay');
      break;
    case 'samples':
      if (!view) throw new Error('fixtures.ids.core_view_ids missing');
      get(`/teacher/visits/${visit}/samples?contentViewId=${view}&limit=2000`,
        teacher, 'GET /teacher/visits/:id/samples');
      break;
    case 'aoi_summary':
      post(`/teacher/courses/${core}/analytics/aoi-summary`, teacher,
        { includeShort: true, surface: 'all' },
        'POST /teacher/courses/:id/analytics/aoi-summary');
      break;
    case 'heatmap':
      post(`/teacher/courses/${core}/analytics/heatmap`, teacher,
        { slideId: ids.core_slide_ids[0], includeShort: true },
        'POST /teacher/courses/:id/analytics/heatmap');
      break;
    case 'export_visit':
      get(`/teacher/visits/${visit}/export`, teacher,
        'GET /teacher/visits/:id/export');
      break;
    case 'export_lesson':
      get(`/teacher/lessons/${ids.core_lesson_ids[0]}/export?scope=slide`, teacher,
        'GET /teacher/lessons/:id/export');
      break;
    case 'publish':
      post(`/teacher/courses/${ids.draft_course_id}/publish`, teacher, {},
        'POST /teacher/courses/:id/publish');
      break;
    case 'quiz':
      get(`/api/lessons/${ids.quiz_lesson_ids[0]}/quiz`, student,
        'GET /api/lessons/:id/quiz');
      break;
    case 'login':
      post('/api/auth/login', '', {
        email: __ENV.LOGIN_EMAIL,
        password: __ENV.LOGIN_PASSWORD,
      }, 'POST /api/auth/login');
      break;
    case 'health':
      get('/health', '', 'GET /health');
      break;
    default:
      throw new Error(`Unknown SCENARIO=${scenario}`);
  }

  if (thinkTime > 0) sleep(thinkTime);
}

function markdown(data) {
  const lines = ['# k6 summary', '', `scenario: ${scenario}`, ''];
  for (const [name, metric] of Object.entries(data.metrics)) {
    if (!name.startsWith('http_req_') && name !== 'iterations' && name !== 'vus') continue;
    const values = metric.values || {};
    const bits = Object.entries(values)
      .filter(([k]) => ['count', 'rate', 'avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'].includes(k))
      .map(([k, v]) => `${k}=${typeof v === 'number' ? v.toFixed(3) : v}`);
    if (bits.length) lines.push(`- ${name}: ${bits.join(', ')}`);
  }
  return lines.join('\n') + '\n';
}

export function handleSummary(data) {
  const base = __ENV.OUT_PREFIX || '/tmp/k6';
  return {
    [`${base}.summary.json`]: JSON.stringify(data, null, 2),
    [`${base}.summary.md`]: markdown(data),
  };
}
