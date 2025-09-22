"use client";

import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/api/client";
import type { ApiError } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { AdminUserSummary, InviteCode, RegistrationSettings, UserGroup } from "@/lib/api/types";

export const adminKeys = {
  all: ["admin"] as const,
  users: () => [...adminKeys.all, "users"] as const,
  groups: () => [...adminKeys.all, "groups"] as const,
  invites: () => [...adminKeys.all, "invites"] as const,
  settings: () => [...adminKeys.all, "settings"] as const,
};

export function useAdminUsersQuery() {
  return useQuery<AdminUserSummary[], ApiError>({
    queryKey: adminKeys.users(),
    queryFn: async () => apiClient.get<AdminUserSummary[]>(endpoints.admin.users),
    staleTime: 30 * 1000,
  });
}

export function useAdminGroupsQuery() {
  return useQuery<UserGroup[], ApiError>({
    queryKey: adminKeys.groups(),
    queryFn: async () => apiClient.get<UserGroup[]>(endpoints.admin.groups),
    staleTime: 5 * 60 * 1000,
  });
}

export function useAdminInvitesQuery() {
  return useQuery<InviteCode[], ApiError>({
    queryKey: adminKeys.invites(),
    queryFn: async () => apiClient.get<InviteCode[]>(endpoints.admin.invites),
    staleTime: 30 * 1000,
  });
}

export function useRegistrationSettingQuery() {
  return useQuery<RegistrationSettings, ApiError>({
    queryKey: adminKeys.settings(),
    queryFn: async () => apiClient.get<RegistrationSettings>(endpoints.admin.settings),
    staleTime: 5 * 60 * 1000,
  });
}
