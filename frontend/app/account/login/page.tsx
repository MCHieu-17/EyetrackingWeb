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
        <h1 className="font-[family-name:var(--font-heading)] text-2xl font-semibold tracking-tight text-foreground">
          Chào mừng trở lại
        </h1>
        <p className="text-sm text-muted-foreground">Đăng nhập để tiếp tục sử dụng Fovea.</p>
      </div>
      <LoginForm />
      <p className="mt-6 text-center text-xs text-muted-foreground">
        Chưa có tài khoản?{" "}
        <Link href="/account/register" className="font-semibold text-foreground underline underline-offset-2">
          Đăng ký với Outlook
        </Link>
      </p>
    </AuthLayout>
  );
}
