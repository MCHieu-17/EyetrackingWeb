import { API_BASE_URL, ApiError } from "@/lib/api/client";
import { postGazeBatch, type GazeBatchInput } from "@/lib/api/student";
import {
  deleteGazeBatch,
  enqueueGazeBatch,
  ensureQueueGeneration,
  gazeBatchQueueId,
  pendingGazeBatches,
  updateGazeBatchAttempt,
  updateGazeBatchGeneration,
} from "@/lib/gaze-queue";

let flushing = false;
let generation: string | null = null;
const queuedFlushes: Array<{ sessionId?: string; keepalive: boolean }> = [];

async function currentGeneration(
  keepIds: readonly string[] = [],
): Promise<string | null> {
  if (generation) return generation;
  try {
    const response = await fetch(`${API_BASE_URL}/api/health`, {
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
    await ensureQueueGeneration(generation, keepIds);
    return generation;
  } catch {
    return null;
  }
}

async function flushPass(
  sessionId: string | undefined,
  keepalive: boolean,
): Promise<void> {
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
}

export async function queueGazeBatch(
  sessionId: string,
  batch: GazeBatchInput,
  keepalive = false,
): Promise<void> {
  // Persist trước khi gọi /health: lúc unload, request health có thể bị hủy
  // nhưng batch vẫn nằm trong IndexedDB cho lần flush sau.
  const id = gazeBatchQueueId(sessionId, batch.batchId);
  await enqueueGazeBatch(sessionId, batch, generation ?? undefined);
  const gen = await currentGeneration([id]);
  if (gen) await updateGazeBatchGeneration(id, gen);
  void flushGazeQueue(sessionId, keepalive);
}

export async function flushGazeQueue(
  sessionId?: string,
  keepalive = false,
): Promise<void> {
  const request = { sessionId, keepalive };
  if (flushing) {
    // Không bỏ request đến trong lúc đang flush; chạy thêm một lượt sau đó để
    // batch vừa enqueue không bị kẹt lại (đặc biệt khi trang sắp unload).
    queuedFlushes.push(request);
    return;
  }
  flushing = true;
  try {
    let next: { sessionId?: string; keepalive: boolean } | undefined = request;
    while (next) {
      await flushPass(next.sessionId, next.keepalive);
      next = queuedFlushes.shift();
    }
  } finally {
    flushing = false;
  }
}
