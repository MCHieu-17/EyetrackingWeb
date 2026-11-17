import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { GazeBatchInput } from "@/lib/api/student";
import type { QueuedGazeBatch } from "@/lib/gaze-queue";

const queueMocks = vi.hoisted(() => ({
  enqueueGazeBatch: vi.fn(),
  ensureQueueGeneration: vi.fn(),
  gazeBatchQueueId: vi.fn(
    (sessionId: string, batchId: string) => `${sessionId}:${batchId}`,
  ),
  pendingGazeBatches: vi.fn(),
  deleteGazeBatch: vi.fn(),
  updateGazeBatchAttempt: vi.fn(),
  updateGazeBatchGeneration: vi.fn(),
}));

const studentMocks = vi.hoisted(() => ({
  postGazeBatch: vi.fn(),
}));

vi.mock("@/lib/gaze-queue", () => queueMocks);
vi.mock("@/lib/api/student", () => studentMocks);

const fetchMock = vi.fn();

function healthResponse(
  schemaGeneration = "gen",
  dbInstanceId = "db",
): Response {
  return new Response(JSON.stringify({ schemaGeneration, dbInstanceId }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function makeBatch(id: string): GazeBatchInput {
  return {
    batchId: `batch-${id}`,
    presentationId: `presentation-${id}`,
    sequenceStart: 0,
    sequenceEnd: 0,
    samples: [],
  };
}

function makeItem(id: string): QueuedGazeBatch {
  return {
    id: `session:batch-${id}`,
    sessionId: "session",
    batch: makeBatch(id),
    createdAt: 1_000,
    attempts: 0,
  };
}

async function loadSender() {
  vi.resetModules();
  const client = await import("@/lib/api/client");
  const sender = await import("./gaze-sender");
  return { ...sender, ApiError: client.ApiError };
}

beforeEach(() => {
  vi.clearAllMocks();
  fetchMock.mockImplementation(async () => healthResponse());
  vi.stubGlobal("fetch", fetchMock);

  queueMocks.enqueueGazeBatch.mockResolvedValue(undefined);
  queueMocks.ensureQueueGeneration.mockResolvedValue(undefined);
  queueMocks.pendingGazeBatches.mockResolvedValue([]);
  queueMocks.deleteGazeBatch.mockResolvedValue(undefined);
  queueMocks.updateGazeBatchAttempt.mockResolvedValue(undefined);
  queueMocks.updateGazeBatchGeneration.mockResolvedValue(undefined);
  studentMocks.postGazeBatch.mockResolvedValue({
    ok: true,
    batchId: "batch",
    received: 0,
    stored: 0,
    duplicate: 0,
    rejected: 0,
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("queueGazeBatch", () => {
  it("persists the batch before looking up /health", async () => {
    const order: string[] = [];
    let resolveHealth!: (response: Response) => void;
    const health = new Promise<Response>((resolve) => {
      resolveHealth = resolve;
    });
    fetchMock.mockImplementation(() => {
      order.push("health");
      return health;
    });
    queueMocks.enqueueGazeBatch.mockImplementation(async () => {
      order.push("enqueue");
    });

    const { queueGazeBatch } = await loadSender();
    const queued = queueGazeBatch("session", makeBatch("1"), true);

    await vi.waitFor(() => expect(order).toEqual(["enqueue", "health"]));
    resolveHealth(healthResponse());
    await queued;

    expect(queueMocks.updateGazeBatchGeneration).toHaveBeenCalledWith(
      "session:batch-1",
      "gen:db",
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/health",
      expect.objectContaining({ credentials: "include" }),
    );
  });
});

describe("flushGazeQueue", () => {
  it("runs a trailing pass requested while another flush is in flight", async () => {
    const first = makeItem("1");
    const second = makeItem("2");
    queueMocks.pendingGazeBatches
      .mockResolvedValueOnce([first])
      .mockResolvedValueOnce([second])
      .mockResolvedValue([]);

    let resolveFirst!: (value: unknown) => void;
    const firstPost = new Promise((resolve) => {
      resolveFirst = resolve;
    });
    studentMocks.postGazeBatch
      .mockImplementationOnce(() => firstPost)
      .mockResolvedValueOnce({ ok: true });

    const { flushGazeQueue } = await loadSender();
    const inFlight = flushGazeQueue("session", true);
    await vi.waitFor(() =>
      expect(studentMocks.postGazeBatch).toHaveBeenCalledTimes(1),
    );

    const trailing = flushGazeQueue("session", true);
    resolveFirst({ ok: true });
    await Promise.all([inFlight, trailing]);

    expect(studentMocks.postGazeBatch).toHaveBeenNthCalledWith(
      1,
      "session",
      first.batch,
      true,
    );
    expect(studentMocks.postGazeBatch).toHaveBeenNthCalledWith(
      2,
      "session",
      second.batch,
      true,
    );
    expect(queueMocks.deleteGazeBatch).toHaveBeenCalledWith(first.id);
    expect(queueMocks.deleteGazeBatch).toHaveBeenCalledWith(second.id);
  });

  it("keeps the same batch ID and payload when retrying a failed post", async () => {
    const item = makeItem("1");
    queueMocks.pendingGazeBatches.mockResolvedValue([item]);
    const { flushGazeQueue, ApiError: LoadedApiError } = await loadSender();
    studentMocks.postGazeBatch
      .mockRejectedValueOnce(new LoadedApiError(500, "temporary"))
      .mockResolvedValueOnce({ ok: true });

    await flushGazeQueue("session");

    expect(queueMocks.updateGazeBatchAttempt).toHaveBeenCalledWith(item.id, 1);
    expect(queueMocks.deleteGazeBatch).not.toHaveBeenCalled();

    await flushGazeQueue("session");

    expect(studentMocks.postGazeBatch).toHaveBeenNthCalledWith(
      1,
      "session",
      item.batch,
      false,
    );
    expect(studentMocks.postGazeBatch).toHaveBeenNthCalledWith(
      2,
      "session",
      item.batch,
      false,
    );
    expect(queueMocks.deleteGazeBatch).toHaveBeenCalledWith(item.id);
  });

  it("deletes a 409 batch and continues with the next one", async () => {
    const conflict = makeItem("1");
    const next = makeItem("2");
    queueMocks.pendingGazeBatches.mockResolvedValue([conflict, next]);
    const { flushGazeQueue, ApiError: LoadedApiError } = await loadSender();
    studentMocks.postGazeBatch
      .mockRejectedValueOnce(new LoadedApiError(409, "conflict"))
      .mockResolvedValueOnce({ ok: true });

    await flushGazeQueue("session");

    expect(queueMocks.deleteGazeBatch).toHaveBeenCalledWith(conflict.id);
    expect(queueMocks.deleteGazeBatch).toHaveBeenCalledWith(next.id);
    expect(queueMocks.updateGazeBatchAttempt).not.toHaveBeenCalled();
    expect(studentMocks.postGazeBatch).toHaveBeenCalledTimes(2);
  });
});
