"use client";

import type { PDFDocumentProxy } from "pdfjs-dist";

let pdfjsPromise: Promise<typeof import("pdfjs-dist")> | null = null;

export function loadPdfjs(): Promise<typeof import("pdfjs-dist")> {
  if (!pdfjsPromise) {
    pdfjsPromise = import("pdfjs-dist").then((pdfjs) => {
      pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
      return pdfjs;
    });
  }
  return pdfjsPromise;
}

const documentCache = new Map<string, Promise<PDFDocumentProxy>>();
const MAX_DOCUMENTS = 4;

/**
 * Cache PDFDocumentProxy theo URL. PDF.js giữ toàn bộ cấu trúc file trong RAM,
 * nên chỉ giữ tối đa vài document; document cũ bị destroy khi vượt ngưỡng.
 */
export function loadPdfDocument(url: string): Promise<PDFDocumentProxy> {
  const cached = documentCache.get(url);
  if (cached) {
    documentCache.delete(url);
    documentCache.set(url, cached);
    return cached;
  }

  const promise = loadPdfjs().then((pdfjs) =>
    pdfjs.getDocument({
      url,
      withCredentials: true,
      // Backend proxy không hỗ trợ Range; tải một lần toàn bộ PDF.
      disableRange: true,
      disableStream: true,
      isEvalSupported: false,
      cMapUrl: "/pdfjs/cmaps/",
      cMapPacked: true,
      standardFontDataUrl: "/pdfjs/standard_fonts/",
      wasmUrl: "/pdfjs/wasm/",
      iccUrl: "/pdfjs/iccs/",
    }).promise,
  );

  documentCache.set(url, promise);
  promise.catch(() => {
    if (documentCache.get(url) === promise) documentCache.delete(url);
  });

  if (documentCache.size > MAX_DOCUMENTS) {
    const oldestKey = documentCache.keys().next().value;
    if (oldestKey) {
      const oldest = documentCache.get(oldestKey);
      documentCache.delete(oldestKey);
      oldest?.then((doc) => doc.destroy()).catch(() => {});
    }
  }

  return promise;
}
