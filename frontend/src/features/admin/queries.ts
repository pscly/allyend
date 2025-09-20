"use client";

import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/api/client";
import type { ApiError } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { AdminUserSummary, InviteCode, RegistrationSettings, UserGroup } from "@/lib/api/types";
import { useAuthStore } from "@/store/auth-store";

export const adminKeys = {
  all: ["admin"] as const,
  users: () => [...adminKeys.all, "users"] as const,
  groups: () => [...adminKeys.all, "groups"] as const,
  invites: () => [...adminKeys.all, "invites"] as const,
  settings: () => [...adminKeys.all, "settings"] as const,
};

export function useAdminUsersQuery() {
  const token = useAuthStore((state) => state.token);

  return useQuery<AdminUserSummary[], ApiError>({
    queryKey: adminKeys.users(),
    enabled: Boolean(token),
    queryFn: async () => apiClient.get<AdminUserSummary[]>(endpoints.admin.users, { token }),
    staleTime: 30 * 1000,
  });
}

export function useAdminGroupsQuery() {
  const token = useAuthStore((state) => state.token);

  return useQuery<UserGroup[], ApiError>({
    queryKey: adminKeys.groups(),
    enabled: Boolean(token),
    queryFn: async () => apiClient.get<UserGroup[]>(endpoints.admin.groups, { token }),
    staleTime: 5 * 60 * 1000,
  });
}

export function useAdminInvitesQuery() {
  const token = useAuthStore((state) => state.token);

  return useQuery<InviteCode[], ApiError>({
    queryKey: adminKeys.invites(),
    enabled: Boolean(token),
    queryFn: async () => apiClient.get<InviteCode[]>(endpoints.admin.invites, { token }),
    staleTime: 30 * 1000,
  });
}

export function useRegistrationSettingQuery() {
  const token = useAuthStore((state) => state.token);

  return useQuery<RegistrationSettings, ApiError>({
    queryKey: adminKeys.settings(),
    enabled: Boolean(token),
    queryFn: async () => apiClient.get<RegistrationSettings>(endpoints.admin.settings, { token }),
    staleTime: 5 * 60 * 1000,
  });
}
