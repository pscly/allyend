"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/api/client";
import type { ApiError } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type {
  ApiKey,
  CrawlerAlertEvent,
  CrawlerAlertRule,
  CrawlerCommand,
  CrawlerConfigAssignment,
  CrawlerConfigFetch,
  CrawlerConfigTemplate,
  CrawlerGroup,
  CrawlerHeartbeat,
  CrawlerLog,
  CrawlerRun,
  CrawlerSummary,
  QuickLink,
} from "@/lib/api/types";

export const crawlerKeys = {
  all: ["crawlers"] as const,
  list: (filters?: Record<string, unknown>) => ["crawlers", "list", filters] as const,
  detail: (id: number | string) => ["crawlers", id, "detail"] as const,
  runs: (id: number | string) => ["crawlers", id, "runs"] as const,
  logs: (id: number | string, limit: number) => ["crawlers", id, "logs", limit] as const,
  heartbeats: (
    id: number | string,
    limit: number,
    start?: string | null,
    end?: string | null,
    maxPoints?: number,
  ) => ["crawlers", id, "heartbeats", limit, start ?? null, end ?? null, maxPoints ?? null] as const,
  commands: (id: number | string, includeFinished: boolean, limit: number) =>
    ["crawlers", id, "commands", includeFinished, limit] as const,
  groups: () => ["crawlers", "groups"] as const,
  configTemplates: () => ["crawlers", "config", "templates"] as const,
  configAssignments: () => ["crawlers", "config", "assignments"] as const,
  configFetch: (id: number | string) => ["crawlers", id, "config"] as const,
  alertRules: () => ["crawlers", "alerts", "rules"] as const,
  alertEvents: (filters?: Record<string, unknown>) => ["crawlers", "alerts", "events", filters] as const,
};

export const apiKeyQueryKeys = {
  all: ["apiKeys"] as const,
};

export const quickLinkKeys = {
  all: ["quickLinks"] as const,
};

export interface CrawlerListFilters {
  status?: "online" | "warning" | "offline";
  statuses?: Array<"online" | "warning" | "offline">;
  groupId?: number | "none";
  groupIds?: Array<number | "none">;
  apiKeyId?: number | "none";
  apiKeyIds?: Array<number>;
  keyword?: string;
}

export interface HeartbeatQueryOptions {
  limit?: number;
  start?: string;
  end?: string;
  maxPoints?: number;
  enabled?: boolean;
}

// 统一使用 Cookie 会话，不再依赖 token 存储

export function useCrawlerGroupsQuery() {
  return useQuery<CrawlerGroup[], ApiError>({
    queryKey: crawlerKeys.groups(),
    queryFn: async () => apiClient.get<CrawlerGroup[]>(endpoints.crawlers.groups.list),
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
    // v5 移除 keepPreviousData，使用 placeholderData 保留上一次数据
    placeholderData: (prev) => prev,
  });

}

export function useConfigTemplatesQuery() {
  return useQuery<CrawlerConfigTemplate[], ApiError>({
    queryKey: crawlerKeys.configTemplates(),
    queryFn: async () => apiClient.get<CrawlerConfigTemplate[]>(endpoints.crawlers.config.templates.list),
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
    placeholderData: (prev) => prev,
  });
}

export function useConfigAssignmentsQuery() {
  return useQuery<CrawlerConfigAssignment[], ApiError>({
    queryKey: crawlerKeys.configAssignments(),
    queryFn: async () => apiClient.get<CrawlerConfigAssignment[]>(endpoints.crawlers.config.assignments.list),
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
    placeholderData: (prev) => prev,
  });
}

export function useCrawlersQuery(filters: CrawlerListFilters = {}) {
  const statusKey = filters.statuses?.length
    ? filters.statuses.join(",")
    : filters.status ?? "";
  const groupKey = filters.groupIds?.length
    ? filters.groupIds.map((value) => (value === "none" ? "none" : String(value))).join(",")
    : filters.groupId !== undefined
      ? filters.groupId === "none"
        ? "none"
        : String(filters.groupId)
      : "";
  const apiKeyKey = filters.apiKeyIds?.length
    ? filters.apiKeyIds.map((value) => String(value)).join(",")
    : typeof filters.apiKeyId === "number"
      ? String(filters.apiKeyId)
      : "";
  const keywordKey = filters.keyword ?? "";

  const searchParams = useMemo(() => {
    const params: Record<string, string> = {};
    if (statusKey) params.status_filter = statusKey;
    if (groupKey) params.group_ids = groupKey;
    if (apiKeyKey) params.api_key_ids = apiKeyKey;
    if (keywordKey) params.keyword = keywordKey;
    return params;
  }, [statusKey, groupKey, apiKeyKey, keywordKey]);

  return useQuery<CrawlerSummary[], ApiError>({
    queryKey: crawlerKeys.list(searchParams),
    queryFn: async () =>
      apiClient.get<CrawlerSummary[]>(endpoints.crawlers.list, {
        searchParams,
      }),
    staleTime: 15 * 1000,
    refetchInterval: 15 * 1000,
    placeholderData: (prev) => prev,
  });
}

export function useCrawlerDetailQuery(crawlerId: number | string, enabled = true) {
  const shouldEnable = enabled && Boolean(crawlerId);
  return useQuery<CrawlerSummary, ApiError>({
    queryKey: crawlerKeys.detail(crawlerId),
    queryFn: async () => apiClient.get<CrawlerSummary>(endpoints.crawlers.detail(crawlerId)),
    enabled: shouldEnable,
    staleTime: 10 * 1000,
    refetchInterval: shouldEnable ? 12 * 1000 : false,
  });
}

export function useCrawlerRunsQuery(crawlerId: number | string, enabled = true) {
  const shouldEnable = enabled;
  return useQuery<CrawlerRun[], ApiError>({
    queryKey: crawlerKeys.runs(crawlerId),
    queryFn: async () => apiClient.get<CrawlerRun[]>(endpoints.crawlers.runs(crawlerId)),
    enabled: shouldEnable,
    staleTime: 10 * 1000,
    refetchInterval: shouldEnable ? 15 * 1000 : false,
    placeholderData: (prev) => prev,
  });
}

export function useCrawlerLogsQuery(crawlerId: number | string, limit = 50, enabled = true) {
  const shouldEnable = enabled;
  return useQuery<CrawlerLog[], ApiError>({
    queryKey: crawlerKeys.logs(crawlerId, limit),
    queryFn: async () =>
      apiClient.get<CrawlerLog[]>(endpoints.crawlers.logs(crawlerId), {
        searchParams: { limit: String(limit) },
      }),
    enabled: shouldEnable,
    staleTime: 8 * 1000,
    refetchInterval: shouldEnable ? 12 * 1000 : false,
    placeholderData: (prev) => prev,
  });
}

export function useCrawlerHeartbeatsQuery(
  crawlerId: number | string,
  options: HeartbeatQueryOptions = {},
) {
  const { limit = 500, start, end, maxPoints = 600, enabled = true } = options;
  const shouldEnable = enabled;

  const searchParams: Record<string, string> = { limit: String(limit) };
  if (start) {
    searchParams.start = start;
  }
  if (end) {
    searchParams.end = end;
  }
  if (maxPoints) {
    searchParams.max_points = String(maxPoints);
  }

  return useQuery<CrawlerHeartbeat[], ApiError>({
    queryKey: crawlerKeys.heartbeats(crawlerId, limit, start ?? null, end ?? null, maxPoints ?? null),
    queryFn: async () =>
      apiClient.get<CrawlerHeartbeat[]>(endpoints.crawlers.heartbeats(crawlerId), {
        searchParams,
      }),
    enabled: shouldEnable,
    staleTime: 8 * 1000,
    refetchInterval: shouldEnable ? 8 * 1000 : false,
    placeholderData: (prev) => prev,
  });
}

export function useCrawlerCommandsQuery(
  crawlerId: number | string,
  includeFinished = false,
  enabled = true,
  options: { limit?: number; refetchInterval?: number | false } = {},
) {
  const limit = options.limit ?? 200;
  const shouldEnable = enabled;
  return useQuery<CrawlerCommand[], ApiError>({
    queryKey: crawlerKeys.commands(crawlerId, includeFinished, limit),
    queryFn: async () =>
      apiClient.get<CrawlerCommand[]>(endpoints.crawlers.commands.list(crawlerId), {
        searchParams: {
          include_finished: includeFinished ? "1" : "0",
          limit: String(limit),
        },
      }),
    enabled: shouldEnable,
    staleTime: 8 * 1000,
    refetchInterval: shouldEnable ? options.refetchInterval ?? 12 * 1000 : false,
    placeholderData: (prev) => prev,
  });

}

export function useCrawlerConfigFetchQuery(crawlerId: number | string, enabled = true) {
  const shouldEnable = enabled && Boolean(crawlerId);
  return useQuery<CrawlerConfigFetch, ApiError>({
    queryKey: crawlerKeys.configFetch(crawlerId),
    queryFn: async () => apiClient.get<CrawlerConfigFetch>(endpoints.crawlers.config.fetch(crawlerId)),
    enabled: shouldEnable,
    staleTime: 30 * 1000,
    refetchInterval: shouldEnable ? 60 * 1000 : false,
  });
}

export function useAlertRulesQuery() {
  return useQuery<CrawlerAlertRule[], ApiError>({
    queryKey: crawlerKeys.alertRules(),
    queryFn: async () => apiClient.get<CrawlerAlertRule[]>(endpoints.crawlers.alerts.rules.list),
    staleTime: 45 * 1000,
    refetchInterval: 45 * 1000,
    placeholderData: (prev) => prev,
  });
}

export interface AlertEventsFilters {
  ruleId?: number;
  status?: string;
  limit?: number;
}

export function useAlertEventsQuery(filters: AlertEventsFilters = {}, enabled = true) {
  const shouldEnable = enabled;
  const searchParams: Record<string, string> = {};
  if (filters.ruleId) searchParams.rule_id = String(filters.ruleId);
  if (filters.status) searchParams.status_filter = filters.status;
  if (filters.limit) searchParams.limit = String(filters.limit);
  return useQuery<CrawlerAlertEvent[], ApiError>({
    queryKey: crawlerKeys.alertEvents(searchParams),
    queryFn: async () => apiClient.get<CrawlerAlertEvent[]>(endpoints.crawlers.alerts.events, { searchParams }),
    enabled: shouldEnable,
    staleTime: 30 * 1000,
    refetchInterval: shouldEnable ? 30 * 1000 : false,
    placeholderData: (prev) => prev,
  });
}

export function useApiKeysQuery(enabled = true) {
  const shouldEnable = enabled;
  return useQuery<ApiKey[], ApiError>({
    queryKey: apiKeyQueryKeys.all,
    queryFn: async () => apiClient.get<ApiKey[]>(endpoints.apiKeys.list),
    enabled: shouldEnable,
    staleTime: 60 * 1000,
    refetchInterval: shouldEnable ? 60 * 1000 : false,
    placeholderData: (prev) => prev,
  });
}

export function useQuickLinksQuery(enabled = true) {
  const shouldEnable = enabled;
  return useQuery<QuickLink[], ApiError>({
    queryKey: quickLinkKeys.all,
    queryFn: async () => apiClient.get<QuickLink[]>(endpoints.crawlers.quickLinks.list),
    enabled: shouldEnable,
    staleTime: 30 * 1000,
    refetchInterval: shouldEnable ? 30 * 1000 : false,
    placeholderData: (prev) => prev,
  });
}
