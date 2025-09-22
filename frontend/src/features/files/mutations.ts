"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/api/client";
import type { ApiError } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { FileEntry, FileToken, FileUploadResponse } from "@/lib/api/types";
import { useAuthStore } from "@/store/auth-store";
import { filesKeys } from "@/features/files/queries";

interface UploadFileInput {
  file: File;
  fileName?: string;
  description?: string;
  visibility?: "private" | "group" | "public" | "disabled";
}

interface UpdateFileInput {
  fileId: number;
  description?: string | null;
  visibility?: "private" | "group" | "public" | "disabled";
}

interface CreateTokenInput {
  token?: string;
  name?: string;
  description?: string;
  allowedIps?: string;
  allowedCidrs?: string;
}

interface UpdateTokenInput {
  tokenId: number;
  name?: string;
  description?: string;
  allowedIps?: string;
  allowedCidrs?: string;
  isActive?: boolean;
}

export function useUploadFileMutation() {
  const queryClient = useQueryClient();

  return useMutation<FileUploadResponse, ApiError, UploadFileInput>({
    mutationFn: async ({ file, fileName, description, visibility = "private" }) => {
      const form = new FormData();
      form.append("file", file);
      form.append("visibility", visibility);
      if (fileName) {
        form.append("file_name", fileName);
      }
      if (description) {
        form.append("description", description);
      }
      return apiClient.post<FileUploadResponse>(endpoints.files.uploadMine, form);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: filesKeys.list() });
    },
  });
}

export function useDeleteFileMutation() {
  const queryClient = useQueryClient();

  return useMutation<{ ok: boolean }, ApiError, number>({
    mutationFn: async (fileId) => apiClient.delete<{ ok: boolean }>(endpoints.files.deleteFile(fileId)),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: filesKeys.list() });
    },
  });
}

export function useUpdateFileMutation() {
  const queryClient = useQueryClient();

  return useMutation<FileEntry, ApiError, UpdateFileInput>({
    mutationFn: async ({ fileId, description, visibility }) =>
      apiClient.patch<FileEntry>(
        endpoints.files.updateFile(fileId),
        {
          description: description ?? undefined,
          visibility,
        },
      ),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: filesKeys.list() }),
        queryClient.invalidateQueries({ queryKey: filesKeys.logs() }),
      ]);
    },
  });
}

export function useCreateTokenMutation() {
  const queryClient = useQueryClient();

  return useMutation<FileToken, ApiError, CreateTokenInput>({
    mutationFn: async ({ token: rawToken, name, description, allowedIps, allowedCidrs }) =>
      apiClient.post<FileToken>(
        endpoints.files.tokens,
        {
          token: rawToken,
          name,
          description,
          allowed_ips: allowedIps,
          allowed_cidrs: allowedCidrs,
        },
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: filesKeys.tokens() });
    },
  });
}

export function useUpdateTokenMutation() {
  const queryClient = useQueryClient();

  return useMutation<FileToken, ApiError, UpdateTokenInput>({
    mutationFn: async ({ tokenId, name, description, allowedIps, allowedCidrs, isActive }) => {
      const form = new FormData();
      if (isActive !== undefined) {
        form.append("is_active", String(isActive));
      }
      if (name !== undefined) {
        form.append("name", name ?? "");
      }
      if (description !== undefined) {
        form.append("description", description ?? "");
      }
      if (allowedIps !== undefined) {
        form.append("allowed_ips", allowedIps ?? "");
      }
      if (allowedCidrs !== undefined) {
        form.append("allowed_cidrs", allowedCidrs ?? "");
      }
      return apiClient.patch<FileToken>(endpoints.files.tokenById(tokenId), form);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: filesKeys.tokens() });
    },
  });
}
