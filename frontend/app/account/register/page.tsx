import type { Metadata } from "next";
import Link from "next/link";
import { AuthLayout } from "@/components/account/auth-layout";
import { RegisterForm } from "@/components/account/register-form";

export const metadata: Metadata = {
  title: "Đăng ký – Fovea",
};

export default function RegisterPage() {
  return (
    <AuthLayout>
      <div className="mb-6 space-y-1.5 text-center lg:text-left">
        <span aria-hidden className="mx-auto block h-1 w-10 rounded-full bg-brand-red lg:mx-0" />
        <h1 className="font-display text-2xl text-foreground">
          Tạo tài khoản
        </h1>
        <p className="text-sm text-muted-foreground">
          Tạo tài khoản sinh viên bằng Outlook và mã OTP.
        </p>
      </div>
      <RegisterForm />
      <p className="mt-6 text-center text-xs text-muted-foreground">
        Đã có tài khoản?{" "}
        <Link href="/account/login" className="font-semibold text-primary underline underline-offset-2 transition-colors hover:text-primary-hover">
          Đăng nhập
        </Link>
      </p>
    </AuthLayout>
  );
}
