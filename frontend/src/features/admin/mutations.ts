"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/api/client";
import type { ApiError } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type {
  AdminUserRole,
  AdminUserSummary,
  InviteCode,
  RegistrationMode,
  RegistrationSettings,
} from "@/lib/api/types";
import { useAuthStore } from "@/store/auth-store";

import { adminKeys } from "./queries";

interface UpdateAdminUserInput {
  userId: number;
  role?: AdminUserRole;
  groupId?: number | null;
  isActive?: boolean;
}

interface CreateInviteInput {
  note?: string | null;
  allowAdmin?: boolean;
  maxUses?: number | null;
  expiresInMinutes?: number | null;
  targetGroupId?: number | null;
}

export function useUpdateAdminUserMutation() {
  const queryClient = useQueryClient();

  return useMutation<AdminUserSummary, ApiError, UpdateAdminUserInput>({
    mutationFn: async ({ userId, role, groupId, isActive }) => {
      const payload: Record<string, unknown> = {};
      if (role !== undefined) {
        payload.role = role;
      }
      if (groupId !== undefined) {
        payload.group_id = groupId;
      }
      if (isActive !== undefined) {
        payload.is_active = isActive;
      }
      return apiClient.patch<AdminUserSummary>(endpoints.admin.userById(userId), payload);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: adminKeys.users() });
    },
  });
}

export function useCreateInviteMutation() {
  const queryClient = useQueryClient();

  return useMutation<InviteCode, ApiError, CreateInviteInput>({
    mutationFn: async ({ note, allowAdmin = false, maxUses = null, expiresInMinutes = null, targetGroupId = null }) =>
      apiClient.post<InviteCode>(
        endpoints.admin.invites,
        {
          note,
          allow_admin: allowAdmin,
          max_uses: maxUses,
          expires_in_minutes: expiresInMinutes,
          target_group_id: targetGroupId,
        },
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: adminKeys.invites() });
    },
  });
}

export function useDeleteInviteMutation() {
  const queryClient = useQueryClient();

  return useMutation<{ ok: boolean }, ApiError, number>({
    mutationFn: async (inviteId) => apiClient.delete<{ ok: boolean }>(endpoints.admin.inviteById(inviteId)),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: adminKeys.invites() });
    },
  });
}

export function useUpdateRegistrationModeMutation() {
  const queryClient = useQueryClient();

  return useMutation<RegistrationSettings, ApiError, RegistrationMode>({
    mutationFn: async (mode) =>
      apiClient.patch<RegistrationSettings>(endpoints.admin.registration, { mode }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: adminKeys.settings() });
    },
  });
}
