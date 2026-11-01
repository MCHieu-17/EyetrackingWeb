import type { NextConfig } from "next";
import path from "path";

// URL nội bộ cho rewrite phía server (không lọt vào client bundle).
// Docker: tên service; dev trên host: localhost (đặt trong .env.local).
const API_URL = process.env.API_INTERNAL_URL?.trim() || "http://backend:8001";
const GAZE_URL = process.env.GAZE_INTERNAL_URL?.trim() || "http://gaze:8000";

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

const isDev = process.env.NODE_ENV !== "production";

// CSP không hardcode domain: lấy từ env + localhost cho dev.
const connectSrc = [
  "'self'",
  "http://localhost:*",
  "ws://localhost:*",
  originOf(PUBLIC_API_URL),
  originOf(PUBLIC_GAZE_URL),
  wsOriginOf(PUBLIC_GAZE_URL),
]
  .filter(Boolean)
  .join(" ");

const scriptSrc = isDev
  ? "'self' 'unsafe-inline' 'unsafe-eval'"
  : "'self' 'unsafe-inline'";

const contentSecurityPolicy = [
  "default-src 'self'",
  `script-src ${scriptSrc}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https:",
  "font-src 'self' data:",
  `connect-src ${connectSrc}`,
  "media-src 'self' blob:",
].join("; ");

const nextConfig: NextConfig = {
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
          { key: "Permissions-Policy", value: "camera=(self), microphone=()" },
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

export default nextConfig;
