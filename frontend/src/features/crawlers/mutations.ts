"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/api/client";
import type { ApiError } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type {
  ApiKey,
  CrawlerAlertRule,
  CrawlerCommand,
  CrawlerConfigAssignment,
  CrawlerConfigTemplate,
  CrawlerGroup,
  CrawlerSummary,
  QuickLink,
} from "@/lib/api/types";
import { crawlerKeys, apiKeyQueryKeys, quickLinkKeys } from "@/features/crawlers/queries";

export interface CreateApiKeyInput {
  name?: string;
  description?: string;
  is_public?: boolean;
  group_id?: number | null;
  allowed_ips?: string | null;
}

export interface UpdateApiKeyInput extends CreateApiKeyInput {
  active?: boolean;
}

export function useCreateApiKeyMutation() {
  const queryClient = useQueryClient();
  return useMutation<ApiKey, ApiError, CreateApiKeyInput>({
    mutationFn: async (payload) => apiClient.post<ApiKey>(endpoints.apiKeys.create, payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: crawlerKeys.all }),
        queryClient.invalidateQueries({ queryKey: crawlerKeys.groups() }),
        queryClient.invalidateQueries({ queryKey: apiKeyQueryKeys.all }),
      ]);
    },
  });
}

export function useUpdateApiKeyMutation() {
  const queryClient = useQueryClient();
  return useMutation<ApiKey, ApiError, { keyId: number | string; payload: UpdateApiKeyInput }>({
    mutationFn: async ({ keyId, payload }) =>
      apiClient.patch<ApiKey>(endpoints.apiKeys.update(keyId), payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: crawlerKeys.all }),
        queryClient.invalidateQueries({ queryKey: apiKeyQueryKeys.all }),
      ]);
    },
  });
}

export function useDeleteApiKeyMutation() {
  const queryClient = useQueryClient();
  return useMutation<{ ok: boolean }, ApiError, number | string>({
    mutationFn: async (keyId) => apiClient.delete(endpoints.apiKeys.delete(keyId)),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: crawlerKeys.all }),
        queryClient.invalidateQueries({ queryKey: apiKeyQueryKeys.all }),
      ]);
    },
  });
}

export function useRotateApiKeyMutation() {
  const queryClient = useQueryClient();
  return useMutation<ApiKey, ApiError, number | string>({
    mutationFn: async (keyId) => apiClient.post<ApiKey>(endpoints.apiKeys.rotate(keyId)),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: crawlerKeys.all }),
        queryClient.invalidateQueries({ queryKey: apiKeyQueryKeys.all }),
      ]);
    },
  });
}

export interface UpdateCrawlerInput {
  name?: string;
  is_public?: boolean;
}

export function useUpdateCrawlerMutation(crawlerId: number | string) {
  const queryClient = useQueryClient();
  return useMutation<CrawlerSummary, ApiError, UpdateCrawlerInput>({
    mutationFn: async (payload) =>
      apiClient.patch<CrawlerSummary>(endpoints.crawlers.detail(crawlerId), payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: crawlerKeys.all });
    },
  });
}

export function useCreateCrawlerCommandMutation(crawlerId: number | string) {
  const queryClient = useQueryClient();
  return useMutation<CrawlerCommand, ApiError, { command: string; payload?: Record<string, unknown>; expires_in_seconds?: number }>(
    {
      mutationFn: async (payload) =>
        apiClient.post<CrawlerCommand>(endpoints.crawlers.commands.create(crawlerId), payload),
      onSuccess: async () => {
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: crawlerKeys.commands(crawlerId, false, 200) }),
          queryClient.invalidateQueries({ queryKey: crawlerKeys.commands(crawlerId, true, 200) }),
        ]);
      },
    },
  );
}

export function useCreateCrawlerGroupMutation() {
  const queryClient = useQueryClient();
  return useMutation<CrawlerGroup, ApiError, { name: string; slug?: string; description?: string; color?: string }>(
    {
      mutationFn: async (payload) =>
        apiClient.post<CrawlerGroup>(endpoints.crawlers.groups.list, payload),
      onSuccess: async () => {
        await queryClient.invalidateQueries({ queryKey: crawlerKeys.groups() });
      },
    },
  );
}

export function useUpdateCrawlerGroupMutation(groupId: number | string) {
  const queryClient = useQueryClient();
  return useMutation<CrawlerGroup, ApiError, { name?: string; slug?: string; description?: string; color?: string }>(
    {
      mutationFn: async (payload) =>
        apiClient.patch<CrawlerGroup>(endpoints.crawlers.groups.byId(groupId), payload),
      onSuccess: async () => {
        await queryClient.invalidateQueries({ queryKey: crawlerKeys.groups() });
        await queryClient.invalidateQueries({ queryKey: crawlerKeys.all });
      },
    },
  );
}

export function useDeleteCrawlerGroupMutation(groupId: number | string) {
  const queryClient = useQueryClient();
  return useMutation<{ ok: boolean }, ApiError>({
    mutationFn: async () => apiClient.delete(endpoints.crawlers.groups.byId(groupId)),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: crawlerKeys.groups() });
      await queryClient.invalidateQueries({ queryKey: crawlerKeys.all });
    },
  });
}



export interface CreateConfigTemplateInput {
  name: string;
  description?: string | null;
  format?: "json" | "yaml";
  content: string;
  is_active?: boolean;
}

export type UpdateConfigTemplateInput = Partial<CreateConfigTemplateInput>;

export interface CreateConfigAssignmentInput {
  name: string;
  description?: string | null;
  target_type: "crawler" | "api_key" | "group";
  target_id: number;
  format?: "json" | "yaml";
  content?: string | null;
  template_id?: number | null;
  is_active?: boolean;
}

export type UpdateConfigAssignmentInput = Partial<CreateConfigAssignmentInput>;

export interface AlertChannelInput {
  type: "email" | "webhook";
  target: string;
  enabled?: boolean;
  note?: string | null;
}

export interface CreateAlertRuleInput {
  name: string;
  description?: string | null;
  trigger_type: "status_offline" | "payload_threshold";
  target_type: "all" | "group" | "crawler" | "api_key";
  target_ids?: number[];
  payload_field?: string | null;
  comparator?: "gt" | "ge" | "lt" | "le" | "eq" | "ne" | null;
  threshold?: number | null;
  consecutive_failures?: number;
  cooldown_minutes?: number;
  channels?: AlertChannelInput[];
  is_active?: boolean;
}

export type UpdateAlertRuleInput = Partial<CreateAlertRuleInput>;

export function useCreateConfigTemplateMutation() {
  const queryClient = useQueryClient();
  return useMutation<CrawlerConfigTemplate, ApiError, CreateConfigTemplateInput>({
    mutationFn: async (payload) => apiClient.post<CrawlerConfigTemplate>(endpoints.crawlers.config.templates.create, payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: crawlerKeys.configTemplates() }),
        queryClient.invalidateQueries({ queryKey: crawlerKeys.configAssignments() }),
      ]);
    },
  });
}

export function useUpdateConfigTemplateMutation() {
  const queryClient = useQueryClient();
  return useMutation<CrawlerConfigTemplate, ApiError, { templateId: number | string; payload: UpdateConfigTemplateInput }>({
    mutationFn: async ({ templateId, payload }) =>
      apiClient.patch<CrawlerConfigTemplate>(endpoints.crawlers.config.templates.byId(templateId), payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: crawlerKeys.configTemplates() }),
        queryClient.invalidateQueries({ queryKey: crawlerKeys.configAssignments() }),
      ]);
    },
  });
}

export function useDeleteConfigTemplateMutation() {
  const queryClient = useQueryClient();
  return useMutation<{ ok: boolean }, ApiError, number | string>({
    mutationFn: async (templateId) => apiClient.delete(endpoints.crawlers.config.templates.byId(templateId)),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: crawlerKeys.configTemplates() }),
        queryClient.invalidateQueries({ queryKey: crawlerKeys.configAssignments() }),
      ]);
    },
  });
}

function invalidateConfigCaches(queryClient: ReturnType<typeof useQueryClient>) {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: crawlerKeys.configAssignments() }),
    queryClient.invalidateQueries({ queryKey: crawlerKeys.configTemplates() }),
    queryClient.invalidateQueries({ queryKey: crawlerKeys.all }),
    queryClient.invalidateQueries({
      predicate: (query) =>
        Array.isArray(query.queryKey) &&
        query.queryKey.length >= 3 &&
        query.queryKey[0] === "crawlers" &&
        query.queryKey[2] === "config",
    }),
  ]);
}

export function useCreateConfigAssignmentMutation() {
  const queryClient = useQueryClient();
  return useMutation<CrawlerConfigAssignment, ApiError, CreateConfigAssignmentInput>({
    mutationFn: async (payload) =>
      apiClient.post<CrawlerConfigAssignment>(endpoints.crawlers.config.assignments.create, payload),
    onSuccess: async () => {
      await invalidateConfigCaches(queryClient);
    },
  });
}

export function useUpdateConfigAssignmentMutation() {
  const queryClient = useQueryClient();
  return useMutation<CrawlerConfigAssignment, ApiError, { assignmentId: number | string; payload: UpdateConfigAssignmentInput }>({
    mutationFn: async ({ assignmentId, payload }) =>
      apiClient.patch<CrawlerConfigAssignment>(endpoints.crawlers.config.assignments.byId(assignmentId), payload),
    onSuccess: async () => {
      await invalidateConfigCaches(queryClient);
    },
  });
}

export function useDeleteConfigAssignmentMutation() {
  const queryClient = useQueryClient();
  return useMutation<{ ok: boolean }, ApiError, number | string>({
    mutationFn: async (assignmentId) => apiClient.delete(endpoints.crawlers.config.assignments.byId(assignmentId)),
    onSuccess: async () => {
      await invalidateConfigCaches(queryClient);
    },
  });
}

function invalidateAlertCaches(queryClient: ReturnType<typeof useQueryClient>) {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: crawlerKeys.alertRules() }),
    queryClient.invalidateQueries({
      predicate: (query) =>
        Array.isArray(query.queryKey) &&
        query.queryKey.length >= 4 &&
        query.queryKey[0] === "crawlers" &&
        query.queryKey[2] === "events",
    }),
  ]);
}

export function useCreateAlertRuleMutation() {
  const queryClient = useQueryClient();
  return useMutation<CrawlerAlertRule, ApiError, CreateAlertRuleInput>({
    mutationFn: async (payload) =>
      apiClient.post<CrawlerAlertRule>(endpoints.crawlers.alerts.rules.create, payload),
    onSuccess: async () => {
      await invalidateAlertCaches(queryClient);
    },
  });
}

export function useUpdateAlertRuleMutation() {
  const queryClient = useQueryClient();
  return useMutation<CrawlerAlertRule, ApiError, { ruleId: number | string; payload: UpdateAlertRuleInput }>({
    mutationFn: async ({ ruleId, payload }) =>
      apiClient.patch<CrawlerAlertRule>(endpoints.crawlers.alerts.rules.byId(ruleId), payload),
    onSuccess: async () => {
      await invalidateAlertCaches(queryClient);
    },
  });
}

export function useDeleteAlertRuleMutation() {
  const queryClient = useQueryClient();
  return useMutation<{ ok: boolean }, ApiError, number | string>({
    mutationFn: async (ruleId) => apiClient.delete(endpoints.crawlers.alerts.rules.byId(ruleId)),
    onSuccess: async () => {
      await invalidateAlertCaches(queryClient);
    },
  });
}

export interface CreateQuickLinkInput {
  target_type: "crawler" | "api_key" | "group";
  target_id: number;
  slug?: string | null;
  description?: string | null;
  allow_logs?: boolean;
}

export interface UpdateQuickLinkInput {
  slug?: string | null;
  description?: string | null;
  allow_logs?: boolean;
  is_active?: boolean;
}

export function useCreateQuickLinkMutation() {
  const queryClient = useQueryClient();
  return useMutation<QuickLink, ApiError, CreateQuickLinkInput>({
    mutationFn: async (payload) =>
      apiClient.post<QuickLink>(endpoints.crawlers.quickLinks.list, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: quickLinkKeys.all });
    },
  });
}

export function useUpdateQuickLinkMutation() {
  const queryClient = useQueryClient();
  return useMutation<QuickLink, ApiError, { linkId: number | string; payload: UpdateQuickLinkInput }>({
    mutationFn: async ({ linkId, payload }) =>
      apiClient.patch<QuickLink>(endpoints.crawlers.quickLinks.byId(linkId), payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: quickLinkKeys.all });
    },
  });
}

export function useDeleteQuickLinkMutation() {
  const queryClient = useQueryClient();
  return useMutation<{ ok: boolean }, ApiError, number | string>({
    mutationFn: async (linkId) => apiClient.delete(endpoints.crawlers.quickLinks.byId(linkId)),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: quickLinkKeys.all });
    },
  });
}


