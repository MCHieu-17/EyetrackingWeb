import { ApiError } from "@/lib/api/client";
import { postGazeBatch, type GazeBatchInput } from "@/lib/api/student";
import {
  deleteGazeBatch,
  enqueueGazeBatch,
  pendingGazeBatches,
  updateGazeBatchAttempt,
} from "@/lib/gaze-queue";

let flushing = false;

export async function queueGazeBatch(
  sessionId: string,
  batch: GazeBatchInput,
  keepalive = false,
): Promise<void> {
  await enqueueGazeBatch(sessionId, batch);
  void flushGazeQueue(sessionId, keepalive);
}

export async function flushGazeQueue(
  sessionId?: string,
  keepalive = false,
): Promise<void> {
  if (flushing) return;
  flushing = true;
  try {
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
