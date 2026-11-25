"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BrandLogo } from "@/components/ui/brand-logo";
import { Icon } from "@/components/ui/icon";
import { NAV_BY_ROLE } from "@/lib/nav";
import { type Role } from "@/lib/api/auth";
import { cn } from "@/lib/utils";

export function Sidebar({
  role,
  onNavigate,
}: {
  role: Role;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const items = NAV_BY_ROLE[role] ?? [];
  const primaryItems = items.filter((item) => !item.href.endsWith("/profile"));
  const accountItems = items.filter((item) => item.href.endsWith("/profile"));

  const renderItems = (entries: typeof items) =>
    entries.map((item) => {
      const active = item.match(pathname);
      return (
        <Link
          key={item.href}
          href={item.href}
          onClick={onNavigate}
          aria-current={active ? "page" : undefined}
          title={item.label}
          className={cn(
            "flex h-11 items-center gap-3 rounded-full px-3.5 transition-colors",
            active
              ? "bg-sidebar-accent text-sidebar-accent-foreground shadow-sm"
              : "text-sidebar-foreground hover:bg-muted hover:text-foreground",
          )}
        >
          <Icon name={item.icon} className="size-5 shrink-0" />
          <span className="whitespace-nowrap text-sm font-medium">{item.label}</span>
        </Link>
      );
    });

  return (
    <div className="flex h-full w-64 flex-col border border-sidebar-border bg-sidebar text-sidebar-foreground shadow-sm">
      <Link
        href={`/${role}`}
        onClick={onNavigate}
        className="flex h-20 shrink-0 items-center gap-3 px-5"
        aria-label="Eyetracking"
      >
        <BrandLogo className="h-10" />
      </Link>

      <nav
        className="mx-3 flex flex-col gap-2 rounded-[22px] p-2"
        aria-label="Điều hướng chính"
      >
        {renderItems(primaryItems)}
      </nav>

      {accountItems.length > 0 && (
        <nav
          className="mx-3 mb-3 mt-auto flex flex-col gap-2 rounded-[22px] p-2"
          aria-label="Tài khoản"
        >
          {renderItems(accountItems)}
        </nav>
      )}

      <p className="mt-auto px-6 pb-6 text-[11px] leading-relaxed text-muted-foreground">
        Eyetracking · NEU
      </p>
    </div>
  );
}
