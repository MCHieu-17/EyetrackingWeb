import { afterEach, describe, expect, it } from "vitest";
import { ApiError, parseApiError, readCsrfToken } from "./client";

function clearCsrfCookie() {
  document.cookie = "csrf_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
}

describe("parseApiError", () => {
  it("reads a string detail and Retry-After", async () => {
    const response = new Response(JSON.stringify({ detail: "Too many requests" }), {
      status: 429,
      headers: { "Retry-After": "12" },
    });

    const error = await parseApiError(response);

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(429);
    expect(error.message).toBe("Too many requests");
    expect(error.retryAfter).toBe(12);
  });

  it("reads an object detail message", async () => {
    const response = new Response(
      JSON.stringify({ detail: { code: "invalid", message: "Bad input" } }),
      { status: 422 },
    );

    const error = await parseApiError(response);

    expect(error.status).toBe(422);
    expect(error.message).toBe("Bad input");
    expect(error.retryAfter).toBeUndefined();
  });

  it("falls back to detail code, then message, then HTTP status", async () => {
    const codeOnly = await parseApiError(
      new Response(JSON.stringify({ detail: { code: "forbidden" } }), { status: 403 }),
    );
    expect(codeOnly.message).toBe("forbidden");

    const messageOnly = await parseApiError(
      new Response(JSON.stringify({ message: "Server exploded" }), { status: 500 }),
    );
    expect(messageOnly.message).toBe("Server exploded");

    const empty = await parseApiError(new Response("{}", { status: 500 }));
    expect(empty.message).toBe("HTTP 500");
  });

  it("handles non-JSON bodies", async () => {
    const error = await parseApiError(new Response("oops", { status: 502 }));

    expect(error.status).toBe(502);
    expect(error.message).toBe("HTTP 502");
  });

  it("ignores invalid or non-positive Retry-After values", async () => {
    const invalid = await parseApiError(
      new Response("{}", { status: 429, headers: { "Retry-After": "soon" } }),
    );
    expect(invalid.retryAfter).toBeUndefined();

    const zero = await parseApiError(
      new Response("{}", { status: 429, headers: { "Retry-After": "0" } }),
    );
    expect(zero.retryAfter).toBeUndefined();
  });
});

describe("readCsrfToken", () => {
  afterEach(clearCsrfCookie);

  it("returns null when the cookie is missing", () => {
    expect(readCsrfToken()).toBeNull();
  });

  it("decodes the cookie value", () => {
    document.cookie = "csrf_token=abc%20def";
    expect(readCsrfToken()).toBe("abc def");
  });
});
