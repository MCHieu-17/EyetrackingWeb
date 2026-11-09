// k6 browse load test: login -> my enrollments -> course outline.
//
//   BASE_URL=http://localhost:3000 k6 run loadtest/browse.js
//
// Tài khoản test phải tồn tại và có ít nhất một khóa học đã publish.

import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:3000";
const EMAIL = __ENV.TEST_EMAIL || "student@school.edu.vn";
const PASSWORD = __ENV.TEST_PASSWORD || "Password123!";

export const options = {
  stages: [
    { duration: "1m", target: 50 },
    { duration: "3m", target: 50 },
    { duration: "1m", target: 100 },
    { duration: "3m", target: 100 },
    { duration: "1m", target: 200 },
    { duration: "3m", target: 200 },
    { duration: "1m", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.01"],
    "http_req_duration{name:enrollments}": ["p(95)<300"],
    "http_req_duration{name:outline}": ["p(95)<300"],
  },
};

export function setup() {
  const login = http.post(
    `${BASE_URL}/api/auth/login`,
    JSON.stringify({ email: EMAIL, password: PASSWORD }),
    { headers: { "Content-Type": "application/json" } },
  );
  check(login, { "login ok": (r) => r.status === 200 });
  const token = login.json("accessToken");
  const headers = { Authorization: `Bearer ${token}` };

  const enrollments = http.get(`${BASE_URL}/api/me/enrollments`, { headers });
  check(enrollments, { "enrollments ok": (r) => r.status === 200 });
  const courses = enrollments.json();
  const courseId = courses.length ? courses[0].course.id : null;
  return { token, courseId };
}

export default function (data) {
  const headers = { Authorization: `Bearer ${data.token}` };

  const enrollments = http.get(`${BASE_URL}/api/me/enrollments`, {
    headers,
    tags: { name: "enrollments" },
  });
  check(enrollments, { "enrollments 200": (r) => r.status === 200 });

  if (data.courseId) {
    const outline = http.get(`${BASE_URL}/api/courses/${data.courseId}`, {
      headers,
      tags: { name: "outline" },
    });
    check(outline, { "outline 200": (r) => r.status === 200 });
  }

  sleep(1);
}
