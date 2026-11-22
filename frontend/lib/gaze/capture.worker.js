/**
 * Encode JPEG cho frame gaze trong worker.
 *
 * Main thread chỉ tạo `ImageBitmap` từ video rồi transfer sang đây; việc
 * resize/draw/encode không chạy trên main thread. Worker giữ một
 * `OffscreenCanvas` để tái sử dụng encoder giữa các frame.
 *
 * Viết JS thuần (không phải .ts) vì Turbopack copy worker asset nguyên văn;
 * file .ts sẽ tới browser với cú pháp TypeScript và không parse được.
 */

/** @typedef {{ id: number, bitmap: ImageBitmap, maxWidth: number, quality: number }} FrameRequest */
/** @typedef {{ id: number, blob?: Blob, error?: string }} FrameReply */

const scope = /** @type {DedicatedWorkerGlobalScope} */ (self);

/** @type {OffscreenCanvas | null} */
let canvas = null;
/** @type {OffscreenCanvasRenderingContext2D | null} */
let context = null;

/**
 * @param {FrameReply} message
 */
function reply(message) {
  scope.postMessage(message);
}

scope.onmessage = async (event) => {
  const { id, bitmap, maxWidth, quality } = event.data;
  try {
    const scale = Math.min(1, maxWidth / bitmap.width);
    const width = Math.max(1, Math.round(bitmap.width * scale));
    const height = Math.max(1, Math.round(bitmap.height * scale));
    if (!canvas) canvas = new OffscreenCanvas(width, height);
    if (canvas.width !== width) canvas.width = width;
    if (canvas.height !== height) canvas.height = height;
    if (!context) context = canvas.getContext("2d");
    if (!context) throw new Error("không tạo được 2d context");

    context.drawImage(bitmap, 0, 0, width, height);
    const blob = await canvas.convertToBlob({
      type: "image/jpeg",
      quality,
    });
    reply({ id, blob });
  } catch (error) {
    reply({
      id,
      error: error instanceof Error ? error.message : "encode thất bại",
    });
  } finally {
    bitmap.close();
  }
};
