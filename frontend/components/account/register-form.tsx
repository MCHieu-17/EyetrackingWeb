"use client";

import * as React from "react";
import { EmailOtpDialog } from "@/components/account/email-otp-dialog";
import { Button } from "@/components/ui/button";
import { MicrosoftLogo } from "@/components/ui/microsoft-logo";
import { cn } from "@/lib/utils";

export function RegisterForm({ className }: { className?: string }) {
  const [otpOpen, setOtpOpen] = React.useState(false);

  return (
    <div className={cn("w-full", className)}>
      <Button
        type="button"
        variant="outline"
        size="lg"
        className="h-12 w-full text-[15px]"
        onClick={() => setOtpOpen(true)}
      >
        <MicrosoftLogo className="size-4" />
        Đăng ký với Outlook
      </Button>

      <p className="mt-4 text-center text-xs leading-5 text-muted-foreground">
        Tài khoản mới được tạo tự động với quyền sinh viên sau khi bạn xác nhận mã OTP.
        Nếu email đã có tài khoản, bạn sẽ đăng nhập luôn.
      </p>

      <EmailOtpDialog open={otpOpen} onOpenChange={setOtpOpen} mode="register" />
    </div>
  );
}
