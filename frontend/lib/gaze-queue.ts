import type { GazeBatchInput } from "@/lib/api/student";

interface QueuedGazeBatch {
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
const MAX_AGE_MS = 10 * 60 * 1000;
const MAX_BYTES = 10 * 1024 * 1024;

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
    id: `${sessionId}:${batch.batchId}`,
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

async function clearGazeQueue(): Promise<void> {
  if (typeof indexedDB === "undefined") return;
  const db = await openDb();
  const tx = db.transaction(STORE, "readwrite");
  tx.objectStore(STORE).clear();
  await txDone(tx);
  db.close();
}

export async function ensureQueueGeneration(generation: string): Promise<void> {
  if (typeof localStorage === "undefined") return;
  const previous = localStorage.getItem(GENERATION_KEY);
  if (previous && previous !== generation) {
    await clearGazeQueue();
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

async function pruneQueue(): Promise<void> {
  const items = await pendingGazeBatches();
  const now = Date.now();
  let total = 0;
  for (const item of items) {
    total += JSON.stringify(item.batch).length;
    if (now - item.createdAt > MAX_AGE_MS || total > MAX_BYTES) {
      await deleteGazeBatch(item.id);
    }
  }
}
