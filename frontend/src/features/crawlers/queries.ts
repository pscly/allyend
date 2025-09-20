"use client";

import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/api/client";
import type { ApiError } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { CrawlerLog, CrawlerRun, CrawlerSummary } from "@/lib/api/types";
import { useAuthStore } from "@/store/auth-store";

export const crawlerKeys = {
  all: ["crawlers"] as const,
  list: () => [...crawlerKeys.all, "list"] as const,
  runs: (id: number | string) => [...crawlerKeys.all, id, "runs"] as const,
  logs: (id: number | string) => [...crawlerKeys.all, id, "logs"] as const,
};

export function useCrawlersQuery() {
  const token = useAuthStore((state) => state.token);

  return useQuery<CrawlerSummary[], ApiError>({
    queryKey: crawlerKeys.list(),
    queryFn: async () => apiClient.get<CrawlerSummary[]>(endpoints.crawlers.list, { token }),
    enabled: Boolean(token),
    staleTime: 30 * 1000,
  });
}

export function useCrawlerRunsQuery(crawlerId: number | string, enabled = true) {
  const token = useAuthStore((state) => state.token);

  return useQuery<CrawlerRun[], ApiError>({
    queryKey: crawlerKeys.runs(crawlerId),
    queryFn: async () => apiClient.get<CrawlerRun[]>(endpoints.crawlers.runs(crawlerId), { token }),
    enabled: Boolean(token) && enabled,
    staleTime: 15 * 1000,
  });
}

export function useCrawlerLogsQuery(crawlerId: number | string, limit = 50, enabled = true) {
  const token = useAuthStore((state) => state.token);

  return useQuery<CrawlerLog[], ApiError>({
    queryKey: [...crawlerKeys.logs(crawlerId), limit],
    queryFn: async () =>
      apiClient.get<CrawlerLog[]>(endpoints.crawlers.logs(crawlerId), {
        token,
        searchParams: { limit },
      }),
    enabled: Boolean(token) && enabled,
    staleTime: 10 * 1000,
  });
}
