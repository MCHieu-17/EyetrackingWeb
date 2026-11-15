"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  createCourseVisit,
  endCourseVisit,
  heartbeatCourseVisit,
} from "@/lib/api/visits";

const VISIT_KEY_PREFIX = "course_visit_key:";
const HEARTBEAT_MS = 60_000;
const END_GRACE_MS = 1_500;

// StrictMode/route transition: huỷ việc kết thúc visit nếu hook được mount lại
// trong thời gian ngắn với cùng visitId.
const pendingEnds = new Map<string, number>();

function visitKeyFor(courseId: string): string {
  const storageKey = `${VISIT_KEY_PREFIX}${courseId}`;
  const existing = globalThis.sessionStorage?.getItem(storageKey);
  if (existing) return existing;
  const key =
    globalThis.crypto?.randomUUID?.() ??
    `visit-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  globalThis.sessionStorage?.setItem(storageKey, key);
  return key;
}

function rotateVisitKey(courseId: string): string {
  const storageKey = `${VISIT_KEY_PREFIX}${courseId}`;
  const key =
    globalThis.crypto?.randomUUID?.() ??
    `visit-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  globalThis.sessionStorage?.setItem(storageKey, key);
  return key;
}

export interface CourseVisitState {
  visitId: string | null;
  ready: boolean;
  error: string | null;
}

/**
 * Tạo/kết thúc "ca học" khi sinh viên vào/rời trang khóa.
 * Visit được dùng chung cho mọi lesson trong cùng lần vào khóa.
 */
export function useCourseVisit({
  courseId,
  enrollmentId,
}: {
  courseId: string;
  enrollmentId: string | null;
}): CourseVisitState {
  const [visitId, setVisitId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const visitIdRef = useRef<string | null>(null);

  const clearPendingEnd = useCallback((id: string) => {
    const timer = pendingEnds.get(id);
    if (timer !== undefined) {
      window.clearTimeout(timer);
      pendingEnds.delete(id);
    }
  }, []);

  useEffect(() => {
    if (!enrollmentId) {
      visitIdRef.current = null;
      return;
    }

    let disposed = false;
    let createdId: string | null = null;

    const create = async () => {
      const key = visitKeyFor(courseId);
      let visit = await createCourseVisit({ enrollmentId, visitKey: key });
      if (visit.status !== "active") {
        // Key cũ đã kết thúc (tab được khôi phục): xoay key và tạo ca mới.
        visit = await createCourseVisit({
          enrollmentId,
          visitKey: rotateVisitKey(courseId),
        });
      }
      if (disposed || visit.status !== "active") return;
      createdId = visit.id;
      visitIdRef.current = visit.id;
      clearPendingEnd(visit.id);
      setVisitId(visit.id);
      setError(null);
    };

    void create().catch(() => {
      if (!disposed) {
        setVisitId(null);
        setError("Không tạo được ca học");
      }
    });

    const heartbeat = window.setInterval(() => {
      const id = visitIdRef.current;
      if (!id || document.visibilityState !== "visible") return;
      void heartbeatCourseVisit(id).catch(() => {});
    }, HEARTBEAT_MS);

    const end = (keepalive: boolean) => {
      const id = visitIdRef.current;
      if (!id) return;
      visitIdRef.current = null;
      void endCourseVisit(id, keepalive).catch(() => {});
    };

    const onPageHide = () => end(true);

    window.addEventListener("pagehide", onPageHide);
    window.addEventListener("beforeunload", onPageHide);

    return () => {
      disposed = true;
      window.clearInterval(heartbeat);
      window.removeEventListener("pagehide", onPageHide);
      window.removeEventListener("beforeunload", onPageHide);

      const id = createdId ?? visitIdRef.current;
      if (!id) return;
      // Không kết thúc ngay: StrictMode/route transition có thể mount lại.
      const timer = window.setTimeout(() => {
        pendingEnds.delete(id);
        if (visitIdRef.current === id) {
          visitIdRef.current = null;
          setVisitId(null);
        }
        void endCourseVisit(id, true).catch(() => {});
      }, END_GRACE_MS);
      pendingEnds.set(id, timer);
    };
  }, [courseId, enrollmentId, clearPendingEnd]);

  const activeVisitId = enrollmentId ? visitId : null;
  return { visitId: activeVisitId, ready: Boolean(activeVisitId), error };
}
