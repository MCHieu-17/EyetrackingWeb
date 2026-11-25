import type { Metadata } from "next";
import { AuthLayout } from "@/components/account/auth-layout";
import { ChangePasswordForm } from "@/components/account/change-password-form";

export const metadata: Metadata = {
  title: "Đổi mật khẩu – Fovea",
};

export default function ChangePasswordPage() {
  return (
    <AuthLayout>
      <div className="mb-6 space-y-1.5 text-center lg:text-left">
        <span aria-hidden className="mx-auto block h-1 w-10 rounded-full bg-brand-red lg:mx-0" />
        <h1 className="font-display text-2xl text-foreground">
          Đổi mật khẩu
        </h1>
        <p className="text-sm text-muted-foreground">
          Cập nhật mật khẩu cho tài khoản Fovea của bạn.
        </p>
      </div>
      <ChangePasswordForm />
    </AuthLayout>
  );
}
