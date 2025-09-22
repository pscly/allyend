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
import { useAuthStore } from "@/store/auth-store";

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

function useToken() {
  return useAuthStore((state) => state.token);
}

export function useCrawlerGroupsQuery() {
  const token = useToken();
  const enabled = Boolean(token);
  return useQuery<CrawlerGroup[], ApiError>({
    queryKey: crawlerKeys.groups(),
    queryFn: async () => apiClient.get<CrawlerGroup[]>(endpoints.crawlers.groups.list, { token }),
    enabled,
    staleTime: 60 * 1000,
    refetchInterval: enabled ? 60 * 1000 : false,
    // v5 移除 keepPreviousData，使用 placeholderData 保留上一次数据
    placeholderData: (prev) => prev,
  });

}

export function useConfigTemplatesQuery() {
  const token = useToken();
  const enabled = Boolean(token);
  return useQuery<CrawlerConfigTemplate[], ApiError>({
    queryKey: crawlerKeys.configTemplates(),
    queryFn: async () => apiClient.get<CrawlerConfigTemplate[]>(endpoints.crawlers.config.templates.list, { token }),
    enabled,
    staleTime: 60 * 1000,
    refetchInterval: enabled ? 60 * 1000 : false,
    placeholderData: (prev) => prev,
  });
}

export function useConfigAssignmentsQuery() {
  const token = useToken();
  const enabled = Boolean(token);
  return useQuery<CrawlerConfigAssignment[], ApiError>({
    queryKey: crawlerKeys.configAssignments(),
    queryFn: async () => apiClient.get<CrawlerConfigAssignment[]>(endpoints.crawlers.config.assignments.list, { token }),
    enabled,
    staleTime: 60 * 1000,
    refetchInterval: enabled ? 60 * 1000 : false,
    placeholderData: (prev) => prev,
  });
}

export function useCrawlersQuery(filters: CrawlerListFilters = {}) {
  const token = useToken();
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

  const enabled = Boolean(token);

  return useQuery<CrawlerSummary[], ApiError>({
    queryKey: crawlerKeys.list(searchParams),
    queryFn: async () =>
      apiClient.get<CrawlerSummary[]>(endpoints.crawlers.list, {
        token,
        searchParams,
      }),
    enabled,
    staleTime: 15 * 1000,
    refetchInterval: enabled ? 15 * 1000 : false,
    placeholderData: (prev) => prev,
  });
}

export function useCrawlerDetailQuery(crawlerId: number | string, enabled = true) {
  const token = useToken();
  const shouldEnable = Boolean(token) && enabled && Boolean(crawlerId);
  return useQuery<CrawlerSummary, ApiError>({
    queryKey: crawlerKeys.detail(crawlerId),
    queryFn: async () =>
      apiClient.get<CrawlerSummary>(endpoints.crawlers.detail(crawlerId), {
        token,
      }),
    enabled: shouldEnable,
    staleTime: 10 * 1000,
    refetchInterval: shouldEnable ? 12 * 1000 : false,
  });
}

export function useCrawlerRunsQuery(crawlerId: number | string, enabled = true) {
  const token = useToken();
  const shouldEnable = Boolean(token) && enabled;
  return useQuery<CrawlerRun[], ApiError>({
    queryKey: crawlerKeys.runs(crawlerId),
    queryFn: async () => apiClient.get<CrawlerRun[]>(endpoints.crawlers.runs(crawlerId), { token }),
    enabled: shouldEnable,
    staleTime: 10 * 1000,
    refetchInterval: shouldEnable ? 15 * 1000 : false,
    placeholderData: (prev) => prev,
  });
}

export function useCrawlerLogsQuery(crawlerId: number | string, limit = 50, enabled = true) {
  const token = useToken();
  const shouldEnable = Boolean(token) && enabled;
  return useQuery<CrawlerLog[], ApiError>({
    queryKey: crawlerKeys.logs(crawlerId, limit),
    queryFn: async () =>
      apiClient.get<CrawlerLog[]>(endpoints.crawlers.logs(crawlerId), {
        token,
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
  const token = useToken();
  const shouldEnable = Boolean(token) && enabled;

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
        token,
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
  const token = useToken();
  const limit = options.limit ?? 200;
  const shouldEnable = Boolean(token) && enabled;
  return useQuery<CrawlerCommand[], ApiError>({
    queryKey: crawlerKeys.commands(crawlerId, includeFinished, limit),
    queryFn: async () =>
      apiClient.get<CrawlerCommand[]>(endpoints.crawlers.commands.list(crawlerId), {
        token,
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
  const token = useToken();
  const shouldEnable = Boolean(token) && enabled && Boolean(crawlerId);
  return useQuery<CrawlerConfigFetch, ApiError>({
    queryKey: crawlerKeys.configFetch(crawlerId),
    queryFn: async () =>
      apiClient.get<CrawlerConfigFetch>(endpoints.crawlers.config.fetch(crawlerId), { token }),
    enabled: shouldEnable,
    staleTime: 30 * 1000,
    refetchInterval: shouldEnable ? 60 * 1000 : false,
  });
}

export function useAlertRulesQuery() {
  const token = useToken();
  const enabled = Boolean(token);
  return useQuery<CrawlerAlertRule[], ApiError>({
    queryKey: crawlerKeys.alertRules(),
    queryFn: async () => apiClient.get<CrawlerAlertRule[]>(endpoints.crawlers.alerts.rules.list, { token }),
    enabled,
    staleTime: 45 * 1000,
    refetchInterval: enabled ? 45 * 1000 : false,
    placeholderData: (prev) => prev,
  });
}

export interface AlertEventsFilters {
  ruleId?: number;
  status?: string;
  limit?: number;
}

export function useAlertEventsQuery(filters: AlertEventsFilters = {}, enabled = true) {
  const token = useToken();
  const shouldEnable = Boolean(token) && enabled;
  const searchParams: Record<string, string> = {};
  if (filters.ruleId) searchParams.rule_id = String(filters.ruleId);
  if (filters.status) searchParams.status_filter = filters.status;
  if (filters.limit) searchParams.limit = String(filters.limit);
  return useQuery<CrawlerAlertEvent[], ApiError>({
    queryKey: crawlerKeys.alertEvents(searchParams),
    queryFn: async () =>
      apiClient.get<CrawlerAlertEvent[]>(endpoints.crawlers.alerts.events, {
        token,
        searchParams,
      }),
    enabled: shouldEnable,
    staleTime: 30 * 1000,
    refetchInterval: shouldEnable ? 30 * 1000 : false,
    placeholderData: (prev) => prev,
  });
}

export function useApiKeysQuery(enabled = true) {
  const token = useToken();
  const shouldEnable = Boolean(token) && enabled;
  return useQuery<ApiKey[], ApiError>({
    queryKey: apiKeyQueryKeys.all,
    queryFn: async () => apiClient.get<ApiKey[]>(endpoints.apiKeys.list, { token }),
    enabled: shouldEnable,
    staleTime: 60 * 1000,
    refetchInterval: shouldEnable ? 60 * 1000 : false,
    placeholderData: (prev) => prev,
  });
}

export function useQuickLinksQuery(enabled = true) {
  const token = useToken();
  const shouldEnable = Boolean(token) && enabled;
  return useQuery<QuickLink[], ApiError>({
    queryKey: quickLinkKeys.all,
    queryFn: async () => apiClient.get<QuickLink[]>(endpoints.crawlers.quickLinks.list, { token }),
    enabled: shouldEnable,
    staleTime: 30 * 1000,
    refetchInterval: shouldEnable ? 30 * 1000 : false,
    placeholderData: (prev) => prev,
  });
}
