"use client";

import { Button } from "@/components/ui/button";
import { MicrosoftLogo } from "@/components/ui/microsoft-logo";
import { startMicrosoftLogin } from "@/lib/api/auth";
import { cn } from "@/lib/utils";

export function RegisterForm({ className }: { className?: string }) {
  return (
    <div className={cn("w-full", className)}>
      <Button
        type="button"
        variant="outline"
        size="lg"
        className="h-12 w-full rounded-full border-[#e8e8e3] bg-white text-[15px] font-semibold text-[#2a2a2a] shadow-none hover:bg-[#f5f6f2]"
        onClick={() => startMicrosoftLogin()}
      >
        <MicrosoftLogo className="size-4" />
        Đăng ký với Outlook
      </Button>

      <p className="mt-4 text-center text-xs leading-5 text-muted-foreground">
        Tài khoản mới được tạo tự động bằng tài khoản Microsoft 365 của trường.
        Tài khoản mặc định có quyền sinh viên.
      </p>
    </div>
  );
}
