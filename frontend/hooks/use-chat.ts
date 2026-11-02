"use client";

import { useCallback, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  deleteChatSession,
  listChatMessages,
  listChatSessions,
  renameChatSession,
  sendChatMessage,
  streamChatMessage,
  type ChatStreamHandlers,
  type SendChatInput,
} from "@/lib/api/chat";

export function useChatSessions(courseId: string | null) {
  return useQuery({
    queryKey: ["chat", "sessions", courseId],
    queryFn: () => listChatSessions(courseId as string),
    enabled: Boolean(courseId),
  });
}

export function useChatMessages(sessionId: string | null) {
  return useQuery({
    queryKey: ["chat", "messages", sessionId],
    queryFn: () => listChatMessages(sessionId as string),
    enabled: Boolean(sessionId),
  });
}

export function useSendChatMessage() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: SendChatInput) => sendChatMessage(input),
    onSuccess: (_reply, input) => {
      client.invalidateQueries({ queryKey: ["chat", "sessions", input.courseId] });
    },
  });
}

export function useRenameChatSession() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ sessionId, title }: { sessionId: string; title: string }) =>
      renameChatSession(sessionId, title),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["chat", "sessions"] });
    },
  });
}

export function useDeleteChatSession() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) => deleteChatSession(sessionId),
    onSuccess: (_data, sessionId) => {
      client.removeQueries({ queryKey: ["chat", "messages", sessionId] });
      client.invalidateQueries({ queryKey: ["chat", "sessions"] });
    },
  });
}

export function useChatStream() {
  const [streaming, setStreaming] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const send = useCallback(
    async (input: SendChatInput, handlers: ChatStreamHandlers) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      setStreaming(true);
      setStatus("routing");
      try {
        await streamChatMessage(
          input,
          {
            ...handlers,
            onStatus: (stage) => {
              setStatus(stage);
              handlers.onStatus?.(stage);
            },
          },
          controller.signal,
        );
      } finally {
        setStreaming(false);
        setStatus(null);
        abortRef.current = null;
      }
    },
    [],
  );

  const abort = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return { streaming, status, send, abort };
}
