"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { EmailOtpDialog } from "@/components/account/email-otp-dialog";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MicrosoftLogo } from "@/components/ui/microsoft-logo";
import { Spinner } from "@/components/ui/spinner";
import { login } from "@/lib/api/auth";
import { resolveRedirect } from "@/lib/auth-redirect";
import { cn } from "@/lib/utils";
import { AUTH_USER_QUERY_KEY } from "@/hooks/use-stored-user";

const inputClass =
  "h-12 rounded-xl border-input bg-card px-4 text-[15px] text-foreground shadow-xs placeholder:text-muted-foreground hover:border-primary/40 focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-ring/25";

export function LoginForm({ className }: { className?: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [showPassword, setShowPassword] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [pending, setPending] = React.useState(false);
  const [otpOpen, setOtpOpen] = React.useState(false);
  const [next, setNext] = React.useState<string | null>(null);

  const handleOpenOtp = () => {
    setNext(new URLSearchParams(window.location.search).get("next"));
    setOtpOpen(true);
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;

    const formData = new FormData(event.currentTarget);
    const email = String(formData.get("email") ?? "").trim();
    const password = String(formData.get("password") ?? "");
    if (!email || !password) return;

    setPending(true);
    setError(null);
    try {
      const result = await login(email, password);
      queryClient.setQueryData(AUTH_USER_QUERY_KEY, result.user);
      const nextPath = new URLSearchParams(window.location.search).get("next");
      const destination = resolveRedirect(result.user, nextPath);
      router.prefetch(destination);
      router.replace(destination);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Đăng nhập thất bại — vui lòng thử lại.",
      );
      setPending(false);
    }
  };

  return (
    <div className={cn("w-full", className)}>
      <form onSubmit={handleSubmit} noValidate className="space-y-5">
        <div className="space-y-2">
          <Label htmlFor="login-email" className="text-[13px] font-semibold text-foreground">
            Email <span className="text-destructive">*</span>
          </Label>
          <Input
            id="login-email"
            name="email"
            type="email"
            autoComplete="username"
            placeholder="ban@truong.edu.vn"
            required
            className={inputClass}
            aria-invalid={error ? true : undefined}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="login-password" className="text-[13px] font-semibold text-foreground">
            Mật khẩu <span className="text-destructive">*</span>
          </Label>
          <div className="relative">
            <Input
              id="login-password"
              name="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              placeholder="Nhập mật khẩu"
              required
              className={cn(inputClass, "pr-12")}
              aria-invalid={error ? true : undefined}
            />
            <button
              type="button"
              aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
              aria-pressed={showPassword}
              onClick={() => setShowPassword((v) => !v)}
              className="absolute right-2 top-1/2 flex size-8 -translate-y-1/2 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Icon name={showPassword ? "ri-eye-off-line" : "ri-eye-line"} className="size-4" />
            </button>
          </div>
        </div>

        {error && (
          <div
            role="alert"
            className="flex items-start gap-2.5 rounded-xl border border-destructive/20 bg-destructive/10 px-3.5 py-3 text-sm leading-5 text-destructive"
          >
            <Icon name="ri-error-warning-line" className="mt-0.5 size-4 shrink-0" />
            <p>{error}</p>
          </div>
        )}

        <Button
          type="submit"
          size="lg"
          className="h-12 w-full text-[15px]"
          disabled={pending}
        >
          {pending && <Spinner />}
          {pending ? "Đang đăng nhập…" : "Đăng nhập"}
        </Button>
      </form>

      <div className="relative my-5">
        <div className="absolute inset-0 flex items-center">
          <span className="w-full border-t border-border" />
        </div>
        <div className="relative flex justify-center text-[11px] font-semibold uppercase tracking-[0.14em]">
          <span className="bg-card px-3 text-muted-foreground">hoặc</span>
        </div>
      </div>

      <Button
        type="button"
        variant="outline"
        size="lg"
        className="h-12 w-full text-[15px]"
        onClick={handleOpenOtp}
      >
        <MicrosoftLogo className="size-4" />
        Đăng nhập với Outlook
      </Button>
      <p className="mt-2 text-center text-xs leading-5 text-muted-foreground">
        Dành cho sinh viên NEU — mã OTP sẽ được gửi tới hộp thư Outlook.
      </p>

      <EmailOtpDialog
        open={otpOpen}
        onOpenChange={setOtpOpen}
        mode="login"
        next={next}
      />
    </div>
  );
}
