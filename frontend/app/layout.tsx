import type { Metadata, Viewport } from "next";
import { Be_Vietnam_Pro, Inter, Source_Sans_3 } from "next/font/google";
import "./globals.css";
import { ThemeSync } from "@/components/theme/theme-sync";
import { cn } from "@/lib/utils";
import { THEME_INIT_SCRIPT } from "@/lib/theme";
import { Providers } from "./providers";

// Source Sans 3 gần với font nhận diện của NEU (Source Sans Pro); Be Vietnam
// Pro cho tiêu đề, dấu tiếng Việt đẹp ở cỡ lớn.
const sourceSans = Source_Sans_3({
  subsets: ["latin", "vietnamese"],
  variable: "--font-sans",
  display: "swap",
});
const beVietnam = Be_Vietnam_Pro({
  subsets: ["latin", "vietnamese"],
  weight: ["600", "700"],
  variable: "--font-heading",
  display: "swap",
});

// Khung reader (trang thu gaze + bản xem trước AOI) giữ font Inter cũ: kích
// thước chữ quyết định box của các [data-aoi] dạng nút/thanh, nên giữ nguyên
// để AOI giao diện so sánh được giữa dữ liệu trước và sau redesign.
// preload=false: chỉ tải khi trang có reader.
const readerFont = Inter({
  subsets: ["latin", "vietnamese"],
  variable: "--font-reader",
  preload: false,
});

export const metadata: Metadata = {
  title: "Eyetracking – Nền tảng học tập phân tích ánh nhìn",
  description:
    "Eyetracking: nền tảng học trực tuyến của Đại học Kinh tế Quốc dân, dùng webcam eye-tracking để hiểu cách người học quan sát từng trang tài liệu.",
  icons: {
    icon: [
      { url: "/brand/neu-emblem-32.png", sizes: "32x32", type: "image/png" },
      { url: "/brand/neu-emblem-192.png", sizes: "192x192", type: "image/png" },
    ],
    apple: [{ url: "/brand/neu-emblem-180.png", sizes: "180x180", type: "image/png" }],
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f5f7fb" },
    { media: "(prefers-color-scheme: dark)", color: "#07111f" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="vi"
      className={cn(sourceSans.variable, beVietnam.variable, readerFont.variable, "h-full")}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="min-h-full bg-background font-sans text-foreground antialiased">
        <ThemeSync />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
