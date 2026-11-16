import type { NextConfig } from "next";
import bundleAnalyzer from "@next/bundle-analyzer";
import { existsSync } from "node:fs";
import path from "path";
import { config as loadEnv } from "dotenv";

// Một nguồn env duy nhất: .env ở gốc repo. Docker build dùng build args
// (không có file .env trong context frontend).
const rootEnv = path.resolve(__dirname, "../.env");
if (existsSync(rootEnv)) loadEnv({ path: rootEnv });

const isDev = process.env.NODE_ENV !== "production";

// URL nội bộ cho rewrite phía server (không lọt vào client bundle).
// Docker: tên service; dev trên host: localhost (có thể override trong .env gốc).
const API_URL =
  process.env.API_INTERNAL_URL?.trim() ||
  (isDev ? "http://localhost:8001" : "http://backend:8001");
const GAZE_URL =
  process.env.GAZE_INTERNAL_URL?.trim() ||
  (isDev ? "http://localhost:8000" : "http://gaze:8000");

// Origin công khai (chỉ cần khi browser gọi thẳng domain, không qua rewrite).
const PUBLIC_API_URL = process.env.NEXT_PUBLIC_API_URL?.trim() || "";
const PUBLIC_GAZE_URL = process.env.NEXT_PUBLIC_GAZE_URL?.trim() || "";

function originOf(raw: string): string | null {
  if (!raw) return null;
  try {
    return new URL(raw).origin;
  } catch {
    return null;
  }
}

function wsOriginOf(raw: string): string | null {
  const origin = originOf(raw);
  if (!origin) return null;
  return origin.replace(/^http:/, "ws:").replace(/^https:/, "wss:");
}

// CSP không hardcode domain: lấy từ env + localhost cho dev.
const connectSrc = [
  "'self'",
  ...(isDev ? ["http://localhost:*", "ws://localhost:*"] : []),
  originOf(PUBLIC_API_URL),
  originOf(PUBLIC_GAZE_URL),
  wsOriginOf(PUBLIC_GAZE_URL),
]
  .filter(Boolean)
  .join(" ");

// PDF.js dùng WebAssembly cho một số bộ giải mã ảnh (JPX...).
const scriptSrc = isDev
  ? "'self' 'unsafe-inline' 'unsafe-eval' 'wasm-unsafe-eval'"
  : "'self' 'unsafe-inline' 'wasm-unsafe-eval'";

const contentSecurityPolicy = [
  "default-src 'self'",
  `script-src ${scriptSrc}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https:",
  "font-src 'self' data:",
  `connect-src ${connectSrc}`,
  "media-src 'self' blob:",
  "frame-ancestors 'none'",
].join("; ");

const nextConfig: NextConfig = {
  // Không tự sinh AGENTS.md/CLAUDE.md khi chạy next dev.
  agentRules: false,
  poweredByHeader: false,
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? "",
    NEXT_PUBLIC_GAZE_URL: process.env.NEXT_PUBLIC_GAZE_URL ?? "",
  },
  // Standalone (chỉ khi build Docker): bundle tối thiểu, chạy `node server.js`.
  // KHÔNG bật trên Vercel: Vercel không hỗ trợ và build sẽ lỗi
  // (ENOENT .next/next-server.js.nft.json). Vercel build không set NEXT_STANDALONE.
  output: process.env.NEXT_STANDALONE === "1" ? "standalone" : undefined,
  turbopack: {
    root: path.resolve(__dirname),
  },
  async redirects() {
    return [
      { source: "/student/my-courses", destination: "/student", permanent: true },
      { source: "/teacher/courses", destination: "/teacher", permanent: true },
      { source: "/admin/courses", destination: "/admin", permanent: true },
    ];
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(self), microphone=(), fullscreen=()",
          },
          { key: "Content-Security-Policy", value: contentSecurityPolicy },
        ],
      },
    ];
  },
  async rewrites() {
    return {
      beforeFiles: [
        {
          source: "/api/teacher/:path*",
          destination: `${API_URL}/teacher/:path*`,
        },
        {
          source: "/api/admin/:path*",
          destination: `${API_URL}/admin/:path*`,
        },
      ],
      afterFiles: [
        {
          source: "/api/:path*",
          destination: `${API_URL}/api/:path*`,
        },
        {
          source: "/media/:path*",
          destination: `${API_URL}/media/:path*`,
        },
        {
          source: "/gaze/:path*",
          destination: `${GAZE_URL}/:path*`,
        },
      ],
      fallback: [],
    };
  },
};

export default bundleAnalyzer({ enabled: process.env.ANALYZE === "true" })(nextConfig);
