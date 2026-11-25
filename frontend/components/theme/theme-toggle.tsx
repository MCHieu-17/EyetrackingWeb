"use client";

import { useSyncExternalStore } from "react";
import { Icon } from "@/components/ui/icon";
import {
  readThemePreference,
  setThemePreference,
  THEME_EVENT,
  type ThemePreference,
} from "@/lib/theme";
import { cn } from "@/lib/utils";

const OPTIONS: Array<{ value: ThemePreference; label: string; icon: string }> = [
  { value: "light", label: "Giao diện sáng", icon: "ri-sun-line" },
  { value: "dark", label: "Giao diện tối", icon: "ri-moon-clear-line" },
  { value: "system", label: "Theo hệ thống", icon: "ri-computer-line" },
];

function subscribe(callback: () => void) {
  window.addEventListener(THEME_EVENT, callback);
  window.addEventListener("storage", callback);
  return () => {
    window.removeEventListener(THEME_EVENT, callback);
    window.removeEventListener("storage", callback);
  };
}

/** Nhóm 3 nút chọn theme (radiogroup), dùng trong menu người dùng/landing. */
export function ThemeToggle({ className }: { className?: string }) {
  const current = useSyncExternalStore(
    subscribe,
    readThemePreference,
    () => "system" as ThemePreference,
  );

  return (
    <div
      role="radiogroup"
      aria-label="Giao diện"
      className={cn(
        "inline-flex items-center gap-0.5 rounded-full border border-border bg-muted p-0.5",
        className,
      )}
    >
      {OPTIONS.map((option) => {
        const active = current === option.value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={option.label}
            title={option.label}
            onClick={() => setThemePreference(option.value)}
            className={cn(
              "grid size-7 place-items-center rounded-full text-muted-foreground transition-colors",
              "hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring",
              active && "bg-card text-primary shadow-xs",
            )}
          >
            <Icon name={option.icon} className="size-4" />
          </button>
        );
      })}
    </div>
  );
}
