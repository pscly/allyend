"use client";

import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import type { PersistQueryClientProviderProps } from "@tanstack/react-query-persist-client";
import { createSyncStoragePersister } from "@tanstack/query-sync-storage-persister";
import type { SyncStoragePersister } from "@tanstack/query-sync-storage-persister";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";

interface Props {
  children: ReactNode;
}

/**
 * 全局 React Query Provider，支持本地缓存持久化与开发者工具
 */
export function QueryProvider({ children }: Props) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            staleTime: 30 * 1000,
            refetchOnWindowFocus: false,
            gcTime: 30 * 60 * 1000,
          },
          mutations: {
            retry: 0,
          },
        },
      }),
  );

  const [persister, setPersister] = useState<SyncStoragePersister | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    try {
      setPersister(
        createSyncStoragePersister({
          storage: window.localStorage,
          key: "allyend-query-cache",
        }),
      );
    } catch (error) {
      console.warn("初始化 Query 持久化失败，将退回内存模式", error);
    }
  }, []);

  const devtools = useMemo(
    () => <ReactQueryDevtools buttonPosition="bottom-left" initialIsOpen={false} />,
    [],
  );

  if (!persister) {
    return (
      <QueryClientProvider client={client}>
        {children}
        {devtools}
      </QueryClientProvider>
    );
  }

  const persistOptions: PersistQueryClientProviderProps["persistOptions"] = {
    persister,
    maxAge: 24 * 60 * 60 * 1000,
    hydrateOptions: {
      defaultOptions: {
        queries: {
          staleTime: 30 * 1000,
        },
      },
    },
  };

  return (
    <PersistQueryClientProvider client={client} persistOptions={persistOptions}>
      {children}
      {devtools}
    </PersistQueryClientProvider>
  );
}
