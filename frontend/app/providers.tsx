"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { subscribeAuthChange } from "@/lib/api/auth";

function AuthCacheSync({ client }: { client: QueryClient }) {
  useEffect(() => subscribeAuthChange(() => client.clear()), [client]);

  return null;
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 120_000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={client}>
      <AuthCacheSync client={client} />
      {children}
    </QueryClientProvider>
  );
}
