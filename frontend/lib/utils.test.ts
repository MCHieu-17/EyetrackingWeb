import { createElement } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import {
  formatDateVN,
  formatDateTimeVN,
  formatShortDate,
  initialsOf,
} from "./utils";

describe("formatDateVN", () => {
  it("formats ISO date-only strings deterministically", () => {
    expect(formatDateVN("2026-11-09")).toBe("09/11/2026");
  });

  it("uses the date prefix of ISO timestamps (no timezone shift)", () => {
    expect(formatDateVN("2026-11-09T23:30:00Z")).toBe("09/11/2026");
  });

  it("falls back to Intl vi-VN for non-ISO strings", () => {
    expect(formatDateVN("November 9, 2026")).toBe("09/11/2026");
  });

  it("returns empty for missing values and the original for invalid input", () => {
    expect(formatDateVN(null)).toBe("");
    expect(formatDateVN(undefined)).toBe("");
    expect(formatDateVN("not-a-date")).toBe("not-a-date");
  });
});

describe("formatDateTimeVN", () => {
  it("formats day/month/hour/minute with Intl vi-VN", () => {
    expect(formatDateTimeVN(new Date(2026, 10, 9, 3, 5).toISOString())).toBe(
      "03:05 09-11",
    );
  });

  it("returns empty for missing values and the original for invalid input", () => {
    expect(formatDateTimeVN(null)).toBe("");
    expect(formatDateTimeVN(undefined)).toBe("");
    expect(formatDateTimeVN("not-a-date")).toBe("not-a-date");
  });
});

describe("formatShortDate", () => {
  it("formats a local date as dd/MM/yyyy", () => {
    expect(formatShortDate(new Date(2026, 10, 9, 12, 0).toISOString())).toBe(
      "09/11/2026",
    );
  });

  it("returns empty for missing values and the original for invalid input", () => {
    expect(formatShortDate(null)).toBe("");
    expect(formatShortDate(undefined)).toBe("");
    expect(formatShortDate("not-a-date")).toBe("not-a-date");
  });
});

describe("initialsOf", () => {
  it("uses the first and last word initials", () => {
    expect(initialsOf("Nguyễn Văn An")).toBe("NA");
  });

  it("uses the first two characters for a single word", () => {
    expect(initialsOf("An")).toBe("AN");
  });

  it("returns ? for empty or missing names", () => {
    expect(initialsOf(null)).toBe("?");
    expect(initialsOf(undefined)).toBe("?");
    expect(initialsOf("   ")).toBe("?");
  });

  it("renders initials in the DOM", async () => {
    const user = userEvent.setup();
    render(createElement("button", { type: "button" }, initialsOf("Nguyễn Văn An")));

    const button = screen.getByRole("button", { name: "NA" });
    await user.click(button);

    expect(button).toBeInTheDocument();
  });
});
