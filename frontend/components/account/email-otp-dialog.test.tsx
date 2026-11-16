import * as React from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AuthUser, OtpChallenge } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { AUTH_USER_QUERY_KEY } from "@/hooks/use-stored-user";
import { EmailOtpDialog } from "./email-otp-dialog";

const mocks = vi.hoisted(() => ({
  requestEmailOtp: vi.fn(),
  verifyEmailOtp: vi.fn(),
  replace: vi.fn(),
  prefetch: vi.fn(),
  setQueryData: vi.fn(),
}));

vi.mock("@/lib/api/auth", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/auth")>();
  return {
    ...actual,
    requestEmailOtp: mocks.requestEmailOtp,
    verifyEmailOtp: mocks.verifyEmailOtp,
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    prefetch: mocks.prefetch,
    replace: mocks.replace,
    push: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@tanstack/react-query", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-query")>();
  return {
    ...actual,
    useQueryClient: () => ({ setQueryData: mocks.setQueryData }),
  };
});

const challenge: OtpChallenge = {
  challengeId: "challenge-1",
  email: "12345678@st.neu.edu.vn",
  expiresAt: "2026-11-16T10:00:00Z",
  resendAfterSeconds: 30,
  delivery: "email",
};

const studentUser: AuthUser = {
  id: "user-1",
  email: "12345678@st.neu.edu.vn",
  roles: ["student"],
  fullName: "Sinh viên NEU",
};

function renderDialog(props: Partial<React.ComponentProps<typeof EmailOtpDialog>> = {}) {
  return render(
    <EmailOtpDialog open onOpenChange={vi.fn()} mode="login" {...props} />,
  );
}

async function submitEmail(email: string) {
  fireEvent.change(screen.getByLabelText(/Email sinh viên/), {
    target: { value: email },
  });
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "Gửi mã OTP" }));
    await Promise.resolve();
  });
}

async function submitCode(code: string) {
  fireEvent.change(screen.getByLabelText(/Mã xác nhận/), {
    target: { value: code },
  });
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "Xác nhận" }));
    await Promise.resolve();
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.requestEmailOtp.mockResolvedValue(challenge);
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("EmailOtpDialog", () => {
  it("báo lỗi định dạng email mà không gọi API", async () => {
    renderDialog();

    await submitEmail("sinhvien@gmail.com");

    expect(
      await screen.findByText(/Email không hợp lệ\. Vui lòng nhập email sinh viên/),
    ).toBeInTheDocument();
    expect(mocks.requestEmailOtp).not.toHaveBeenCalled();
  });

  it("gửi OTP và chuyển sang bước nhập mã với email được che bớt", async () => {
    renderDialog();

    await submitEmail("12345678@st.neu.edu.vn");

    expect(await screen.findByLabelText(/Mã xác nhận/)).toBeInTheDocument();
    expect(mocks.requestEmailOtp).toHaveBeenCalledWith("12345678@st.neu.edu.vn");
    expect(screen.getByText("12******@st.neu.edu.vn")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Xác nhận" })).toBeDisabled();
    expect(
      screen.getByText(/kiểm tra thêm mục Thư rác\/Quarantine/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "mở Outlook" }),
    ).toHaveAttribute("href", "https://outlook.office.com/mail/");
  });

  it("hiển thị thông báo khi mã xác nhận sai", async () => {
    mocks.verifyEmailOtp.mockRejectedValue(
      new ApiError(400, "otp_invalid", undefined, {
        code: "otp_invalid",
        message: "Mã xác nhận không đúng. Vui lòng kiểm tra lại.",
      }),
    );
    renderDialog();

    await submitEmail("12345678@st.neu.edu.vn");
    await submitCode("111111");

    expect(
      await screen.findByText("Mã xác nhận không đúng. Vui lòng kiểm tra lại."),
    ).toBeInTheDocument();
    expect(mocks.verifyEmailOtp).toHaveBeenCalledWith("challenge-1", "111111");
    expect(mocks.replace).not.toHaveBeenCalled();
  });

  it("xác nhận đúng mã thì lưu user và chuyển tới next hợp lệ", async () => {
    mocks.verifyEmailOtp.mockResolvedValue({
      accessToken: "access-token",
      refreshToken: "refresh-token",
      user: studentUser,
    });
    renderDialog({ next: "/student/courses/course-1" });

    await submitEmail("12345678@st.neu.edu.vn");
    await submitCode("123456");

    await waitFor(() => {
      expect(mocks.replace).toHaveBeenCalledWith("/student/courses/course-1");
    });
    expect(mocks.setQueryData).toHaveBeenCalledWith(AUTH_USER_QUERY_KEY, studentUser);
    expect(mocks.prefetch).toHaveBeenCalledWith("/student/courses/course-1");
  });

  it("đếm ngược thời gian trước khi cho gửi lại mã", async () => {
    vi.useFakeTimers({
      toFake: ["setTimeout", "clearTimeout", "setInterval", "clearInterval"],
    });
    mocks.requestEmailOtp.mockResolvedValue({ ...challenge, resendAfterSeconds: 2 });
    renderDialog();

    await submitEmail("12345678@st.neu.edu.vn");

    const resendButton = () => screen.getByRole("button", { name: /Gửi lại mã/ });
    expect(resendButton()).toBeDisabled();
    expect(resendButton()).toHaveTextContent("Gửi lại mã (2s)");

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(resendButton()).toBeDisabled();
    expect(resendButton()).toHaveTextContent("Gửi lại mã (1s)");

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(resendButton()).toBeEnabled();
    expect(resendButton()).toHaveTextContent(/^Gửi lại mã$/);

    await act(async () => {
      fireEvent.click(resendButton());
      await Promise.resolve();
    });
    expect(mocks.requestEmailOtp).toHaveBeenCalledTimes(2);
  });
});
