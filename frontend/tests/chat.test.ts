import { afterEach, describe, expect, it, vi } from "vitest";
import { parseFrame, streamChatMessage } from "@/lib/api/chat";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("parseFrame", () => {
  it("parses token event", () => {
    const tokens: string[] = [];
    parseFrame('event: token\ndata: {"text":"Xin chào"}', {
      onToken: (text) => tokens.push(text),
    });
    expect(tokens).toEqual(["Xin chào"]);
  });

  it("parses citations event", () => {
    const citations: unknown[] = [];
    parseFrame(
      'event: citations\ndata: {"citations":[{"documentId":"s1","title":"Bài 1","location":"/media/s1.jpg"}]}',
      { onCitations: (items) => citations.push(...items) },
    );
    expect(citations).toHaveLength(1);
  });

  it("parses done event", () => {
    const done: unknown[] = [];
    parseFrame(
      'event: done\ndata: {"sessionId":"s1","messageId":"m1","intent":"course_qa","verified":true}',
      { onDone: (data) => done.push(data) },
    );
    expect(done).toEqual([
      { sessionId: "s1", messageId: "m1", intent: "course_qa", verified: true },
    ]);
  });

  it("ignores malformed data", () => {
    const tokens: string[] = [];
    parseFrame("event: token\ndata: not-json", {
      onToken: (text) => tokens.push(text),
    });
    expect(tokens).toEqual([]);
  });
});

describe("streamChatMessage", () => {
  it("forwards SSE events to handlers", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(
          encoder.encode('event: session\ndata: {"sessionId":"s1"}\n\n'),
        );
        controller.enqueue(
          encoder.encode('event: status\ndata: {"stage":"retrieving"}\n\n'),
        );
        controller.enqueue(
          encoder.encode(
            'event: citations\ndata: {"citations":[{"documentId":"s1","title":"Bài 1","location":"/media/s1.jpg"}]}\n\n',
          ),
        );
        controller.enqueue(
          encoder.encode('event: token\ndata: {"text":"Xin chào"}\n\n'),
        );
        controller.enqueue(
          encoder.encode(
            'event: done\ndata: {"sessionId":"s1","intent":"course_qa","verified":true}\n\n',
          ),
        );
        controller.close();
      },
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(stream, { status: 200 })),
    );

    const events: string[] = [];
    const tokens: string[] = [];
    await streamChatMessage(
      { courseId: "c1", message: "Khóa chính là gì?" },
      {
        onSession: (id) => events.push(`session:${id}`),
        onStatus: (stage) => events.push(`status:${stage}`),
        onCitations: (items) => events.push(`citations:${items.length}`),
        onToken: (text) => tokens.push(text),
        onDone: (data) => events.push(`done:${data.intent}`),
      },
    );

    expect(events).toEqual([
      "session:s1",
      "status:retrieving",
      "citations:1",
      "done:course_qa",
    ]);
    expect(tokens).toEqual(["Xin chào"]);
  });

  it("throws ApiError on non-200", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("boom", { status: 503 })),
    );

    await expect(
      streamChatMessage({ courseId: "c1", message: "hi" }, {}),
    ).rejects.toThrow();
  });
});

it("sends draft selections without changing or dropping the last question", async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response('event: done\ndata: {"verified":true}\n\n'));
  vi.stubGlobal("fetch", fetchMock);
  const draftAnswers = { q1: ["a"], q5: ["b"], q10: ["c"] };
  await streamChatMessage({ courseId: "c", message: "Gợi ý", assignmentId: "quiz", draftAnswers }, {});
  const body = JSON.parse(fetchMock.mock.calls[0][1].body);
  expect(body.draftAnswers).toEqual(draftAnswers);
  expect(body).not.toHaveProperty("supportMode");
});

it("reports an access revocation SSE error", () => {
  const onError = vi.fn();
  parseFrame('event: error\ndata: {"message":"Chatbot bị khóa","status":403}', { onError });
  expect(onError).toHaveBeenCalledWith("Chatbot bị khóa");
});
