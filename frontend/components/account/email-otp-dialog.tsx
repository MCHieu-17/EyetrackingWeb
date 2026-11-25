"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MicrosoftLogo } from "@/components/ui/microsoft-logo";
import { Spinner } from "@/components/ui/spinner";
import { requestEmailOtp, verifyEmailOtp, type OtpChallenge } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { resolveRedirect } from "@/lib/auth-redirect";
import { cn } from "@/lib/utils";
import { AUTH_USER_QUERY_KEY } from "@/hooks/use-stored-user";

const STUDENT_EMAIL_PATTERN = /^\d{8}@st\.neu\.edu\.vn$/i;
const EMAIL_FORMAT_ERROR =
  "Email không hợp lệ. Vui lòng nhập email sinh viên dạng 12345678@st.neu.edu.vn.";
const GENERIC_ERROR = "Không thể xác thực email. Vui lòng thử lại.";

const inputClass =
  "h-12 rounded-xl border-input bg-card px-4 text-[15px] text-foreground shadow-xs placeholder:text-muted-foreground hover:border-primary/40 focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-ring/25";

const OTP_ERROR_MESSAGES: Record<string, string> = {
  email_not_allowed: EMAIL_FORMAT_ERROR,
  invalid_email: EMAIL_FORMAT_ERROR,
  otp_cooldown: "Bạn vừa yêu cầu mã. Vui lòng chờ vài giây rồi thử lại.",
  otp_rate_limited: "Bạn đã thử quá nhiều lần. Vui lòng chờ một lát rồi thử lại.",
  otp_invalid: "Mã xác nhận không đúng. Vui lòng kiểm tra lại.",
  otp_expired: "Mã xác nhận đã hết hạn. Vui lòng gửi lại mã mới.",
  otp_consumed: "Mã xác nhận đã được sử dụng. Vui lòng gửi lại mã mới.",
  otp_too_many_attempts:
    "Bạn đã nhập sai quá số lần cho phép. Vui lòng gửi lại mã mới.",
  email_not_configured:
    "Hệ thống chưa cấu hình gửi email xác nhận. Vui lòng liên hệ quản trị viên.",
  email_send_failed: "Không gửi được email xác nhận. Vui lòng thử lại sau.",
  account_disabled: "Tài khoản đã bị khóa. Vui lòng liên hệ quản trị viên.",
  otp_config_error:
    "Cấu hình xác thực email chưa hợp lệ. Vui lòng liên hệ quản trị viên.",
  otp_conflict: "Không thể hoàn tất đăng nhập. Vui lòng thử lại.",
  generic: GENERIC_ERROR,
};

function normalizedEmail(value: string): string {
  return value.trim().toLowerCase();
}

function isStudentEmail(value: string): boolean {
  return STUDENT_EMAIL_PATTERN.test(value.trim());
}

function maskedEmail(email: string): string {
  const [local, domain] = email.split("@");
  if (!local || !domain) return email;
  const visible = local.slice(0, 2);
  const hidden = "*".repeat(Math.max(2, local.length - visible.length));
  return `${visible}${hidden}@${domain}`;
}

function errorCode(error: ApiError): string | null {
  // apiFetch trả `detail` là toàn bộ body JSON; backend bọc mã lỗi trong
  // `{ detail: { code, message } }`. Hỗ trợ cả dạng phẳng để test/consumer cũ.
  const body = error.detail;
  const detail =
    body && typeof body === "object" && "detail" in body
      ? (body as { detail?: unknown }).detail
      : body;
  if (detail && typeof detail === "object" && "code" in detail) {
    const code = (detail as { code?: unknown }).code;
    if (typeof code === "string" && code) return code;
  }
  if (typeof detail === "string" && detail in OTP_ERROR_MESSAGES) return detail;
  if (error.message in OTP_ERROR_MESSAGES) return error.message;
  return null;
}

function otpErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const code = errorCode(error);
    if (code) return OTP_ERROR_MESSAGES[code] ?? GENERIC_ERROR;
    if (error.status === 429) return OTP_ERROR_MESSAGES.otp_rate_limited;
    const message = error.message?.trim();
    if (message && message !== `HTTP ${error.status}`) return message;
    return GENERIC_ERROR;
  }
  if (error instanceof Error && error.message.trim()) return error.message;
  return GENERIC_ERROR;
}

type Step = "email" | "code";

export interface EmailOtpDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "login" | "register";
  next?: string | null;
}

export function EmailOtpDialog({ open, onOpenChange, mode, next }: EmailOtpDialogProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [step, setStep] = React.useState<Step>("email");
  const [email, setEmail] = React.useState("");
  const [challenge, setChallenge] = React.useState<OtpChallenge | null>(null);
  const [code, setCode] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [notice, setNotice] = React.useState<string | null>(null);
  const [requesting, setRequesting] = React.useState(false);
  const [verifying, setVerifying] = React.useState(false);
  const [resending, setResending] = React.useState(false);
  const [secondsLeft, setSecondsLeft] = React.useState(0);

  const reset = React.useCallback(() => {
    setStep("email");
    setEmail("");
    setChallenge(null);
    setCode("");
    setError(null);
    setNotice(null);
    setRequesting(false);
    setVerifying(false);
    setResending(false);
    setSecondsLeft(0);
  }, []);

  // Mỗi lần mở/đóng hộp thoại đều bắt đầu từ bước email, không giữ mã cũ.
  // Điều chỉnh state ngay trong render (React cho phép) để không cascade effect.
  const [lastOpen, setLastOpen] = React.useState(open);
  if (open !== lastOpen) {
    setLastOpen(open);
    reset();
  }

  React.useEffect(() => {
    if (!open || step !== "code" || secondsLeft <= 0) return;
    const timer = window.setTimeout(() => {
      setSecondsLeft((current) => Math.max(0, current - 1));
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [open, step, secondsLeft]);

  const handleRequest = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (requesting || resending || verifying) return;

    const target = normalizedEmail(email);
    if (!isStudentEmail(target)) {
      setError(EMAIL_FORMAT_ERROR);
      setNotice(null);
      return;
    }

    setRequesting(true);
    setError(null);
    setNotice(null);
    try {
      const result = await requestEmailOtp(target);
      setEmail(result.email || target);
      setChallenge(result);
      setSecondsLeft(Math.max(0, Math.floor(Number(result.resendAfterSeconds) || 0)));
      setCode("");
      setStep("code");
      setNotice(
        "Đã gửi mã. Nếu không thấy, hãy kiểm tra thêm mục Thư rác/Quarantine.",
      );
    } catch (caught) {
      setError(otpErrorMessage(caught));
    } finally {
      setRequesting(false);
    }
  };

  const handleVerify = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!challenge || verifying || resending) return;
    if (code.length !== 6) {
      setError("Vui lòng nhập đủ 6 chữ số của mã xác nhận.");
      return;
    }

    setVerifying(true);
    setError(null);
    setNotice(null);
    try {
      const result = await verifyEmailOtp(challenge.challengeId, code);
      queryClient.setQueryData(AUTH_USER_QUERY_KEY, result.user);
      const destination = resolveRedirect(result.user, next ?? null);
      router.prefetch(destination);
      router.replace(destination);
    } catch (caught) {
      setError(otpErrorMessage(caught));
      setVerifying(false);
    }
  };

  const handleResend = async () => {
    if (!challenge || resending || requesting || verifying || secondsLeft > 0) return;

    setResending(true);
    setError(null);
    setNotice(null);
    try {
      const result = await requestEmailOtp(email);
      setEmail(result.email || email);
      setChallenge(result);
      setSecondsLeft(Math.max(0, Math.floor(Number(result.resendAfterSeconds) || 0)));
      setCode("");
      setNotice("Đã gửi lại mã xác nhận.");
    } catch (caught) {
      setError(otpErrorMessage(caught));
      if (caught instanceof ApiError && caught.retryAfter) {
        setSecondsLeft(caught.retryAfter);
      }
    } finally {
      setResending(false);
    }
  };

  const handleChangeEmail = () => {
    setStep("email");
    setChallenge(null);
    setCode("");
    setError(null);
    setNotice(null);
    setSecondsLeft(0);
  };

  const busy = requesting || verifying || resending;
  const shownEmail = challenge?.email || email;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md gap-0 overflow-y-auto p-0">
        <DialogHeader className="gap-3 border-b border-border p-6 pr-14 pb-4">
          <span className="flex size-10 items-center justify-center rounded-xl border border-border bg-accent text-accent-foreground">
            <MicrosoftLogo className="size-5" />
          </span>
          <div className="space-y-1">
            <DialogTitle className="text-base font-semibold">
              {step === "email"
                ? mode === "register"
                  ? "Đăng ký với Outlook"
                  : "Đăng nhập với Outlook"
                : "Nhập mã xác nhận"}
            </DialogTitle>
            <DialogDescription>
              {step === "email"
                ? "Mã OTP 6 số sẽ được gửi tới hộp thư Outlook của bạn."
                : "Mã xác nhận đã được gửi tới hộp thư Outlook của bạn."}
            </DialogDescription>
          </div>
        </DialogHeader>

        {step === "email" ? (
          <form onSubmit={handleRequest} noValidate className="space-y-4 p-6 pt-4">
            <div className="space-y-2">
              <Label htmlFor="email-otp-email" className="text-[13px] font-semibold text-foreground">
                Email sinh viên <span className="text-destructive">*</span>
              </Label>
              <Input
                id="email-otp-email"
                name="email"
                type="email"
                inputMode="email"
                autoComplete="email"
                placeholder="12345678@st.neu.edu.vn"
                value={email}
                onChange={(event) => {
                  setEmail(event.target.value);
                  if (error) setError(null);
                }}
                disabled={busy}
                aria-invalid={error ? true : undefined}
                className={inputClass}
              />
              <p className="text-xs leading-5 text-muted-foreground">
                Chỉ nhận email trường @st.neu.edu.vn. Nếu không thấy mã, hãy kiểm
                tra cả mục Thư rác/Quarantine.
              </p>
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
              disabled={busy}
            >
              {requesting && <Spinner />}
              {requesting ? "Đang gửi mã…" : "Gửi mã OTP"}
            </Button>
          </form>
        ) : (
          <form onSubmit={handleVerify} noValidate className="space-y-4 p-6 pt-4">
            <div className="space-y-2">
              <Label htmlFor="email-otp-code" className="text-[13px] font-semibold text-foreground">
                Mã xác nhận <span className="text-destructive">*</span>
              </Label>
              <p className="text-xs leading-5 text-muted-foreground">
                Đã gửi tới{" "}
                <span className="font-medium text-foreground">{maskedEmail(shownEmail)}</span>.
              </p>
              <Input
                id="email-otp-code"
                name="code"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                pattern="[0-9]{6}"
                maxLength={6}
                placeholder="000000"
                value={code}
                onChange={(event) => {
                  setCode(event.target.value.replace(/\D/g, "").slice(0, 6));
                  if (error) setError(null);
                }}
                disabled={busy}
                aria-invalid={error ? true : undefined}
                aria-describedby="email-otp-code-hint"
                className={cn(inputClass, "h-14 text-center font-mono text-2xl tracking-[0.35em]")}
              />
              <p id="email-otp-code-hint" className="text-xs leading-5 text-muted-foreground">
                Nhập 6 chữ số trong email rồi bấm Xác nhận. Thư có thể mất 1–2
                phút;{" "}
                <a
                  href="https://outlook.office.com/mail/"
                  target="_blank"
                  rel="noreferrer"
                  className="font-medium text-foreground underline-offset-2 hover:underline"
                >
                  mở Outlook
                </a>
                .
                {challenge?.delivery === "dev"
                  ? " Môi trường phát triển: mã OTP được ghi trong log backend."
                  : ""}
              </p>
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

            {notice && (
              <p role="status" className="text-xs font-medium text-success">
                {notice}
              </p>
            )}

            <Button
              type="submit"
              size="lg"
              className="h-12 w-full text-[15px]"
              disabled={busy || code.length !== 6}
            >
              {verifying && <Spinner />}
              {verifying ? "Đang xác nhận…" : "Xác nhận"}
            </Button>

            <div className="flex flex-wrap items-center justify-between gap-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="px-2 text-[13px]"
                onClick={handleResend}
                disabled={busy || secondsLeft > 0}
              >
                {resending && <Spinner />}
                {resending
                  ? "Đang gửi lại…"
                  : secondsLeft > 0
                    ? `Gửi lại mã (${secondsLeft}s)`
                    : "Gửi lại mã"}
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="px-2 text-[13px]"
                onClick={handleChangeEmail}
                disabled={busy}
              >
                Đổi email
              </Button>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
