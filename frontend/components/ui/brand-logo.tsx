import Image from "next/image";
import { cn } from "@/lib/utils";

type BrandLogoVariant = "full" | "icon";

/**
 * Lockup Eyetracking: logo NEU chính thức (nguồn: ai.neu.edu.vn) + wordmark.
 * Logo gốc có nền trong suốt; trong theme tối đặt trên một đĩa trắng nhỏ để
 * giữ đúng màu nhận diện của trường.
 */
export function BrandLogo({
  variant = "full",
  className,
  plate = false,
  wordmarkClassName,
}: {
  variant?: BrandLogoVariant;
  className?: string;
  plate?: boolean;
  wordmarkClassName?: string;
}) {
  const iconOnly = variant === "icon";
  return (
    <span
      role="img"
      aria-label="Eyetracking – Đại học Kinh tế Quốc dân"
      className={cn(
        "inline-flex h-9 shrink-0 items-center gap-2 text-brand-navy dark:text-white",
        className,
      )}
    >
      <span
        className={cn(
          "flex h-full shrink-0 items-center justify-center",
          plate ? "rounded-full bg-white p-0.5" : "dark:rounded-full dark:bg-white dark:p-0.5",
        )}
      >
        <Image
          src="/brand/neu-emblem.webp"
          alt=""
          width={250}
          height={249}
          unoptimized
          draggable={false}
          className="h-full w-auto object-contain"
        />
      </span>
      {!iconOnly && (
        <span
          aria-hidden
          className={cn(
            "font-display text-[1.32em] leading-none font-bold tracking-[-0.03em]",
            wordmarkClassName,
          )}
        >
          Eyetracking
        </span>
      )}
    </span>
  );
}
