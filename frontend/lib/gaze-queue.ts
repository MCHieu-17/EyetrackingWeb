import type { GazeBatchInput } from "@/lib/api/student";

export interface QueuedGazeBatch {
  id: string;
  sessionId: string;
  batch: GazeBatchInput;
  createdAt: number;
  attempts: number;
  generation?: string;
}

const DB_NAME = "eyelearning-gaze";
const STORE = "batches";
const GENERATION_KEY = "eyelearning-gaze-generation";
const GAZE_QUEUE_MAX_AGE_MS = 10 * 60 * 1000;
const GAZE_QUEUE_MAX_BYTES = 10 * 1024 * 1024;

export function gazeBatchQueueId(sessionId: string, batchId: string): string {
  return `${sessionId}:${batchId}`;
}

const textEncoder =
  typeof TextEncoder === "undefined" ? null : new TextEncoder();

/** Ước lượng byte UTF-8 thật của payload thay vì đếm ký tự UTF-16. */
export function estimateGazeBatchBytes(batch: GazeBatchInput): number {
  const raw = JSON.stringify(batch);
  if (textEncoder) return textEncoder.encode(raw).length;
  // Fallback cho môi trường cũ: đếm code point và số byte UTF-8 tương ứng.
  let bytes = 0;
  for (const char of raw) {
    const code = char.codePointAt(0) ?? 0;
    bytes +=
      code <= 0x7f ? 1 : code <= 0x7ff ? 2 : code <= 0xffff ? 3 : 4;
  }
  return bytes;
}

/**
 * Chọn các batch cần xóa khi dọn queue.
 *
 * Chính sách:
 * - Luôn xóa batch quá hạn (tuổi > maxAgeMs).
 * - Nếu vượt hạn mức byte, xóa từ batch cũ nhất sang mới nhất cho tới khi
 *   tổng byte còn lại <= maxBytes. Nhờ vậy các batch mới nhất được giữ lại;
 *   không xóa batch mới chỉ vì batch cũ đã chiếm gần hết hạn mức.
 * - Một batch đơn lẻ lớn hơn maxBytes vẫn bị xóa vì không thể nằm trong hạn mức.
 */
export function selectGazeQueueEvictions(
  items: readonly QueuedGazeBatch[],
  now = Date.now(),
  limits: { maxAgeMs?: number; maxBytes?: number } = {},
): QueuedGazeBatch[] {
  const maxAgeMs = limits.maxAgeMs ?? GAZE_QUEUE_MAX_AGE_MS;
  const maxBytes = limits.maxBytes ?? GAZE_QUEUE_MAX_BYTES;
  const evicted: QueuedGazeBatch[] = [];
  const remaining: QueuedGazeBatch[] = [];
  for (const item of items) {
    if (now - item.createdAt > maxAgeMs) evicted.push(item);
    else remaining.push(item);
  }

  remaining.sort(
    (a, b) => a.createdAt - b.createdAt || a.id.localeCompare(b.id),
  );
  let total = remaining.reduce(
    (sum, item) => sum + estimateGazeBatchBytes(item.batch),
    0,
  );
  for (const item of remaining) {
    if (total <= maxBytes) break;
    evicted.push(item);
    total -= estimateGazeBatchBytes(item.batch);
  }
  return evicted;
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: "id" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function txDone(tx: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error);
  });
}

export async function enqueueGazeBatch(
  sessionId: string,
  batch: GazeBatchInput,
  generation?: string,
): Promise<void> {
  if (typeof indexedDB === "undefined") return;
  const db = await openDb();
  const tx = db.transaction(STORE, "readwrite");
  const store = tx.objectStore(STORE);
  const item: QueuedGazeBatch = {
    id: gazeBatchQueueId(sessionId, batch.batchId),
    sessionId,
    batch,
    createdAt: Date.now(),
    attempts: 0,
    generation,
  };
  store.put(item);
  await txDone(tx);
  db.close();
  await pruneQueue();
}

async function clearGazeQueue(
  keepIds: readonly string[] = [],
): Promise<void> {
  if (typeof indexedDB === "undefined") return;
  const db = await openDb();
  const tx = db.transaction(STORE, "readwrite");
  const store = tx.objectStore(STORE);
  if (keepIds.length === 0) {
    store.clear();
  } else {
    const keep = new Set(keepIds);
    const request = store.openCursor();
    request.onsuccess = () => {
      const cursor = request.result;
      if (!cursor) return;
      if (!keep.has(String(cursor.key))) cursor.delete();
      cursor.continue();
    };
  }
  await txDone(tx);
  db.close();
}

/**
 * Đổi generation của DB. Batch cũ thuộc DB instance cũ bị xóa, trừ các id
 * vừa được persist trong request hiện tại (tránh mất batch khi đang unload).
 */
export async function ensureQueueGeneration(
  generation: string,
  keepIds: readonly string[] = [],
): Promise<void> {
  if (typeof localStorage === "undefined") return;
  const previous = localStorage.getItem(GENERATION_KEY);
  if (previous && previous !== generation) {
    await clearGazeQueue(keepIds);
  }
  localStorage.setItem(GENERATION_KEY, generation);
}

export async function pendingGazeBatches(
  sessionId?: string,
): Promise<QueuedGazeBatch[]> {
  if (typeof indexedDB === "undefined") return [];
  const db = await openDb();
  const tx = db.transaction(STORE, "readonly");
  const store = tx.objectStore(STORE);
  const all = await new Promise<QueuedGazeBatch[]>((resolve, reject) => {
    const request = store.getAll();
    request.onsuccess = () => resolve(request.result as QueuedGazeBatch[]);
    request.onerror = () => reject(request.error);
  });
  await txDone(tx);
  db.close();
  return all
    .filter((item) => !sessionId || item.sessionId === sessionId)
    .sort((a, b) => a.createdAt - b.createdAt);
}

export async function deleteGazeBatch(id: string): Promise<void> {
  if (typeof indexedDB === "undefined") return;
  const db = await openDb();
  const tx = db.transaction(STORE, "readwrite");
  tx.objectStore(STORE).delete(id);
  await txDone(tx);
  db.close();
}

export async function updateGazeBatchAttempt(
  id: string,
  attempts: number,
): Promise<void> {
  if (typeof indexedDB === "undefined") return;
  const db = await openDb();
  const tx = db.transaction(STORE, "readwrite");
  const store = tx.objectStore(STORE);
  const item = await new Promise<QueuedGazeBatch | undefined>((resolve, reject) => {
    const request = store.get(id);
    request.onsuccess = () => resolve(request.result as QueuedGazeBatch | undefined);
    request.onerror = () => reject(request.error);
  });
  if (item) store.put({ ...item, attempts });
  await txDone(tx);
  db.close();
}

export async function updateGazeBatchGeneration(
  id: string,
  generation: string,
): Promise<void> {
  if (typeof indexedDB === "undefined") return;
  const db = await openDb();
  const tx = db.transaction(STORE, "readwrite");
  const store = tx.objectStore(STORE);
  const item = await new Promise<QueuedGazeBatch | undefined>((resolve, reject) => {
    const request = store.get(id);
    request.onsuccess = () => resolve(request.result as QueuedGazeBatch | undefined);
    request.onerror = () => reject(request.error);
  });
  if (item) store.put({ ...item, generation });
  await txDone(tx);
  db.close();
}

async function pruneQueue(): Promise<void> {
  const items = await pendingGazeBatches();
  const evicted = selectGazeQueueEvictions(items);
  for (const item of evicted) {
    await deleteGazeBatch(item.id);
  }
}
