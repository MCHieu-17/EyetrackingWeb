import { cn } from "@/lib/utils";

type BrandLogoVariant = "full" | "icon";

/**
 * Logo Fovea: con mắt cách điệu, đồng tử là điểm hội tụ (fovea) màu đỏ NEU
 * trên nền navy NEU. Wordmark dùng font heading + `currentColor` nên tự đổi
 * theo theme sáng/tối. Inline SVG: không thêm request ảnh.
 */
export function BrandLogo({
  variant = "full",
  className,
}: {
  variant?: BrandLogoVariant;
  className?: string;
}) {
  const iconOnly = variant === "icon";
  return (
    <span
      role="img"
      aria-label="Fovea"
      className={cn(
        "inline-flex h-7 shrink-0 items-center gap-2 text-brand-navy",
        className,
      )}
    >
      <FoveaMark className="h-full w-auto" />
      {!iconOnly && (
        <span
          aria-hidden
          className="font-display text-[1.32em] leading-none font-bold tracking-[-0.03em]"
        >
          Fovea
        </span>
      )}
    </span>
  );
}

function FoveaMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" aria-hidden className={className}>
      <rect width="48" height="48" rx="12" fill="#084C90" />
      <path
        d="M6 24c4.8-7.2 10.8-10.8 18-10.8S37.2 16.8 42 24c-4.8 7.2-10.8 10.8-18 10.8S10.8 31.2 6 24Z"
        fill="none"
        stroke="#fff"
        strokeWidth="3"
        strokeLinejoin="round"
      />
      <circle cx="24" cy="24" r="7.2" fill="none" stroke="#fff" strokeWidth="2.6" opacity=".55" />
      <circle cx="24" cy="24" r="3.8" fill="#E8394F" />
    </svg>
  );
}
