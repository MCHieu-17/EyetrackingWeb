import Link from "next/link";
import { BrandLogo } from "@/components/ui/brand-logo";
import { Icon } from "@/components/ui/icon";

const HIGHLIGHTS = [
  { icon: "ri-focus-2-line", text: "Theo dõi hành vi mắt theo từng trang slide" },
  { icon: "ri-bar-chart-box-line", text: "Phân tích mức độ tập trung cho giảng viên" },
  { icon: "ri-rocket-2-line", text: "Calibration nhanh, học ngay trên trình duyệt" },
];

/**
 * Khung hai cột cho trang tài khoản: cột trái là panel thương hiệu luôn nền
 * navy (nên dùng được `text-white/…` cố định), cột phải là form trên `bg-card`.
 */
export function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen bg-background p-3 font-sans text-foreground sm:p-5 lg:grid-cols-[minmax(0,1.05fr)_minmax(420px,0.95fr)] lg:gap-5">
      <aside className="relative hidden flex-col justify-between overflow-hidden rounded-3xl bg-linear-to-br from-navy-800 to-navy-950 px-10 py-10 text-white shadow-md lg:flex xl:px-14 xl:py-12">
        <div
          aria-hidden
          className="pointer-events-none absolute -right-24 -top-24 size-80 rounded-full bg-white/10 blur-3xl"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -bottom-28 -left-20 size-72 rounded-full bg-brand-red/20 blur-3xl"
        />

        <Link
          href="/"
          aria-label="Về trang chủ Eyetracking"
          className="relative w-fit rounded-md outline-none transition-opacity hover:opacity-80 focus-visible:ring-2 focus-visible:ring-white/70 focus-visible:ring-offset-4 focus-visible:ring-offset-navy-900"
        >
          {/* Logo nằm trên nền navy nên wordmark luôn sáng, không theo theme. */}
          <BrandLogo className="h-12 text-white" plate />
        </Link>

        <div className="relative max-w-xl">
          <div className="mb-7 flex items-center gap-2.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-white/70">
            <span aria-hidden className="h-0.5 w-5 rounded-full bg-brand-red" />
            Học tập dựa trên dữ liệu
          </div>
          <h1 className="font-display max-w-lg text-[2.65rem] leading-[1.08] tracking-[-0.04em] text-white xl:text-5xl">
            Hiểu cách người học tập trung.
          </h1>
          <p className="mt-5 max-w-lg text-[15px] leading-7 text-white/75">
            Eyetracking kết hợp webcam và eye-tracking để mang lại trải nghiệm học tập cá nhân
            hóa cùng phân tích trực quan cho giảng viên.
          </p>
          <ul className="mt-9 grid gap-2.5">
            {HIGHLIGHTS.map((item, index) => (
              <li
                key={item.text}
                className="flex items-center gap-4 rounded-2xl border border-white/15 bg-white/10 px-4 py-3.5 text-sm font-medium text-white shadow-xs backdrop-blur"
              >
                <span className="flex size-9 shrink-0 items-center justify-center rounded-xl border border-white/15 bg-white/10 text-white">
                  <Icon name={item.icon} className="size-4" />
                </span>
                <span className="flex-1">{item.text}</span>
                <span className="text-[10px] font-semibold tabular-nums text-white/50">
                  0{index + 1}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="relative flex items-center justify-between border-t border-white/15 pt-5 text-[11px] text-white/60">
          <p>© {new Date().getFullYear()} Eyetracking</p>
          <p className="flex items-center gap-2">
            <Icon name="ri-shield-check-line" className="size-3.5 text-white/80" />
            Dữ liệu gaze được xử lý bảo mật
          </p>
        </div>
      </aside>

      <main className="flex min-h-[calc(100vh-1.5rem)] items-center justify-center rounded-3xl border border-border bg-card px-5 py-8 shadow-sm sm:min-h-[calc(100vh-2.5rem)] sm:px-8 sm:py-12 lg:min-h-0 lg:px-10 xl:px-16">
        <div className="w-full max-w-[420px]">
          <div className="mb-10 flex items-center justify-between border-b border-border pb-5 lg:hidden">
            <Link
              href="/"
              aria-label="Về trang chủ Eyetracking"
              className="rounded-md outline-none transition-opacity hover:opacity-75 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-4"
            >
              <BrandLogo className="h-10" />
            </Link>
            <span className="rounded-full border border-border bg-muted px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              Đăng nhập
            </span>
          </div>
          <div className="[&>div:first-child>h1]:!font-sans">{children}</div>
        </div>
      </main>
    </div>
  );
}
