import { describe, expect, it } from "vitest";
import type { GazeBatchInput } from "@/lib/api/student";
import {
  estimateGazeBatchBytes,
  selectGazeQueueEvictions,
  type QueuedGazeBatch,
} from "./gaze-queue";

function makeBatch(presentationId: string): GazeBatchInput {
  return {
    batchId: `batch-${presentationId}`,
    batchNo: 0,
    presentationId,
    sequenceStart: 0,
    sequenceEnd: 0,
    payloadHash: "hash",
    samples: [],
  };
}

function makeItem(
  id: string,
  createdAt: number,
  presentationId = id,
): QueuedGazeBatch {
  return {
    id,
    sessionId: "session",
    batch: makeBatch(presentationId),
    createdAt,
    attempts: 0,
  };
}

describe("estimateGazeBatchBytes", () => {
  it("counts real UTF-8 bytes, not UTF-16 code units", () => {
    const batch = makeBatch("bài-😀");
    const raw = JSON.stringify(batch);

    expect(estimateGazeBatchBytes(batch)).toBe(
      new TextEncoder().encode(raw).length,
    );
    expect(estimateGazeBatchBytes(batch)).toBeGreaterThan(raw.length);
  });
});

describe("selectGazeQueueEvictions", () => {
  it("removes expired batches regardless of size", () => {
    const expired = makeItem("expired", 1_000);
    const fresh = makeItem("fresh", 9_000);

    const evicted = selectGazeQueueEvictions([expired, fresh], 10_000, {
      maxAgeMs: 5_000,
      maxBytes: 1_000_000,
    });

    expect(evicted).toEqual([expired]);
  });

  it("evicts oldest batches first and keeps the newest under the byte cap", () => {
    const old = makeItem("old", 1_000, "old");
    const middle = makeItem("middle", 2_000, "middle");
    const newest = makeItem("newest", 3_000, "newest");
    const middleAndNewestBytes =
      estimateGazeBatchBytes(middle.batch) + estimateGazeBatchBytes(newest.batch);

    const evicted = selectGazeQueueEvictions([newest, old, middle], 4_000, {
      maxAgeMs: 60_000,
      maxBytes: middleAndNewestBytes,
    });

    expect(evicted.map((item) => item.id)).toEqual(["old"]);
  });

  it("keeps evicting from oldest to newest until the cap is met", () => {
    const old = makeItem("old", 1_000, "old");
    const middle = makeItem("middle", 2_000, "middle");
    const newest = makeItem("newest", 3_000, "newest");

    const evicted = selectGazeQueueEvictions([old, middle, newest], 4_000, {
      maxAgeMs: 60_000,
      maxBytes: estimateGazeBatchBytes(newest.batch),
    });

    expect(evicted.map((item) => item.id)).toEqual(["old", "middle"]);
  });

  it("sorts by createdAt instead of relying on store order", () => {
    const old = makeItem("old", 1_000, "old");
    const middle = makeItem("middle", 2_000, "middle");
    const newest = makeItem("newest", 3_000, "newest");

    const evicted = selectGazeQueueEvictions([newest, middle, old], 4_000, {
      maxAgeMs: 60_000,
      maxBytes: estimateGazeBatchBytes(newest.batch),
    });

    expect(evicted.map((item) => item.id)).toEqual(["old", "middle"]);
  });
});
