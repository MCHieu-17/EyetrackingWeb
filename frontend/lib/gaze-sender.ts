import { API_BASE_URL, ApiError } from "@/lib/api/client";
import { postGazeBatch, type GazeBatchInput } from "@/lib/api/student";
import {
  deleteGazeBatch,
  enqueueGazeBatch,
  ensureQueueGeneration,
  pendingGazeBatches,
  updateGazeBatchAttempt,
} from "@/lib/gaze-queue";

let flushing = false;
let generation: string | null = null;

async function currentGeneration(): Promise<string | null> {
  if (generation) return generation;
  try {
    const response = await fetch(`${API_BASE_URL}/health`, {
      credentials: "include",
      cache: "no-store",
    });
    if (!response.ok) return null;
    const data = (await response.json()) as {
      schemaGeneration?: string | null;
      dbInstanceId?: string | null;
    };
    if (!data.schemaGeneration || !data.dbInstanceId) return null;
    generation = `${data.schemaGeneration}:${data.dbInstanceId}`;
    await ensureQueueGeneration(generation);
    return generation;
  } catch {
    return null;
  }
}

export async function queueGazeBatch(
  sessionId: string,
  batch: GazeBatchInput,
  keepalive = false,
): Promise<void> {
  const gen = await currentGeneration();
  await enqueueGazeBatch(sessionId, batch, gen ?? undefined);
  void flushGazeQueue(sessionId, keepalive);
}

export async function flushGazeQueue(
  sessionId?: string,
  keepalive = false,
): Promise<void> {
  if (flushing) return;
  flushing = true;
  try {
    await currentGeneration();
    const pending = await pendingGazeBatches(sessionId);
    for (const item of pending) {
      try {
        await postGazeBatch(item.sessionId, item.batch, keepalive);
        await deleteGazeBatch(item.id);
      } catch (error) {
        if (error instanceof ApiError && error.status === 409) {
          // Batch ID/payload conflict: giữ queue sẽ lặp vô hạn; bỏ batch này.
          await deleteGazeBatch(item.id);
          continue;
        }
        await updateGazeBatchAttempt(item.id, item.attempts + 1);
        break;
      }
    }
  } finally {
    flushing = false;
  }
}
