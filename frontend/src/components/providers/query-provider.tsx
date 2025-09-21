"use client";

import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { DefaultOptions, HydrateOptions } from "@tanstack/react-query";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import type { PersistQueryClientProviderProps } from "@tanstack/react-query-persist-client";
import type { Persister } from "@tanstack/query-persist-client-core";
import { createSyncStoragePersister } from "@tanstack/query-sync-storage-persister";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";

const QUERY_RETRY_COUNT = 1;
const QUERY_STALE_TIME_MS = 30 * 1000;
const QUERY_GC_TIME_MS = 30 * 60 * 1000;
const PERSIST_MAX_AGE_MS = 24 * 60 * 60 * 1000;

type QueryDefaults = NonNullable<DefaultOptions["queries"]>;
type HydrationQueryOptions = NonNullable<
  NonNullable<HydrateOptions["defaultOptions"]>["queries"]
>;

const createQueryDefaults = (): QueryDefaults => ({
  retry: QUERY_RETRY_COUNT,
  staleTime: QUERY_STALE_TIME_MS,
  refetchOnWindowFocus: false,
  gcTime: QUERY_GC_TIME_MS,
});

const createHydrationQueryDefaults = (): HydrationQueryOptions => ({
  retry: QUERY_RETRY_COUNT,
  gcTime: QUERY_GC_TIME_MS,
});

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
          queries: createQueryDefaults(),
          mutations: {
            retry: 0,
          },
          hydrate: {
            queries: createHydrationQueryDefaults(),
          },
        },
      }),
  );

  const [persister, setPersister] = useState<Persister | null>(null);

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

  const persistOptions = useMemo<PersistQueryClientProviderProps["persistOptions"] | null>(() => {
    if (!persister) {
      return null;
    }
    return {
      persister,
      maxAge: PERSIST_MAX_AGE_MS,
      hydrateOptions: {
        defaultOptions: {
          queries: createHydrationQueryDefaults(),
        },
      },
    };
  }, [persister]);

  if (!persistOptions) {
    return (
      <QueryClientProvider client={client}>
        {children}
        {devtools}
      </QueryClientProvider>
    );
  }

  return (
    <PersistQueryClientProvider client={client} persistOptions={persistOptions}>
      {children}
      {devtools}
    </PersistQueryClientProvider>
  );
}
