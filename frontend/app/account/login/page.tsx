import type { Metadata } from "next";
import Link from "next/link";
import { AuthLayout } from "@/components/account/auth-layout";
import { LoginForm } from "@/components/account/login-form";

export const metadata: Metadata = {
  title: "Đăng nhập – Fovea",
};

export default function LoginPage() {
  return (
    <AuthLayout>
      <div className="mb-6 space-y-1.5 text-center lg:text-left">
        <span aria-hidden className="mx-auto block h-1 w-10 rounded-full bg-brand-red lg:mx-0" />
        <h1 className="font-display text-2xl text-foreground">
          Chào mừng trở lại
        </h1>
        <p className="text-sm text-muted-foreground">Đăng nhập để tiếp tục sử dụng Fovea.</p>
      </div>
      <LoginForm />
      <p className="mt-6 text-center text-xs text-muted-foreground">
        Chưa có tài khoản?{" "}
        <Link href="/account/register" className="font-semibold text-primary underline underline-offset-2 transition-colors hover:text-primary-hover">
          Đăng ký với Outlook
        </Link>
      </p>
    </AuthLayout>
  );
}
