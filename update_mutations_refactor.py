from pathlib import Path

path = Path("frontend/src/features/crawlers/mutations.ts")
text = path.read_text(encoding="utf-8")

def replace_block(source: str, marker: str, new_block: str) -> str:
  start = source.index(marker)
  brace_count = 0
  end = start
  for idx in range(start, len(source)):
    char = source[idx]
    if char == '{':
      brace_count += 1
    elif char == '}':
      brace_count -= 1
      if brace_count == 0 and idx > start:
        end = idx + 1
        break
  return source[:start] + new_block + source[end:]

if "export function useUpdateApiKeyMutation" not in text:
  raise SystemExit("marker for update api key not found")
text = replace_block(text, "export function useUpdateApiKeyMutation", "export function useUpdateApiKeyMutation() {\n  const queryClient = useQueryClient();\n  return useMutation<ApiKey, ApiError, { keyId: number | string; payload: UpdateApiKeyInput }>({\n    mutationFn: async ({ keyId, payload }) =>\n      apiClient.patch<ApiKey>(endpoints.apiKeys.update(keyId), payload),\n    onSuccess: async () => {\n      await Promise.all([\n        queryClient.invalidateQueries({ queryKey: crawlerKeys.all }),\n        queryClient.invalidateQueries({ queryKey: apiKeyQueryKeys.all }),\n      ]);\n    },\n  });\n}\n\n")

if "export function useDeleteApiKeyMutation" not in text:
  raise SystemExit("marker for delete api key not found")
text = text.replace(
  "export function useDeleteApiKeyMutation(keyId: number | string) {",
  "export function useDeleteApiKeyMutation() {",
  1,
)
text = text.replace(
  "mutationFn: async () => apiClient.delete(endpoints.apiKeys.delete(keyId))",
  "mutationFn: async (keyId) => apiClient.delete(endpoints.apiKeys.delete(keyId))",
  1,
)

if "export function useRotateApiKeyMutation" not in text:
  raise SystemExit("marker for rotate api key not found")
text = text.replace(
  "export function useRotateApiKeyMutation(keyId: number | string) {",
  "export function useRotateApiKeyMutation() {",
  1,
)
text = text.replace(
  "mutationFn: async () => apiClient.post<ApiKey>(endpoints.apiKeys.rotate(keyId))",
  "mutationFn: async (keyId) => apiClient.post<ApiKey>(endpoints.apiKeys.rotate(keyId))",
  1,
)

text = text.replace(
  "return useMutation<{ ok: boolean }, ApiError>({",
  "return useMutation<{ ok: boolean }, ApiError, number | string>({",
  1,
)
text = text.replace(
  "return useMutation<ApiKey, ApiError>({",
  "return useMutation<ApiKey, ApiError, number | string>({",
  1,
)

if "export function useUpdateQuickLinkMutation" not in text:
  raise SystemExit("marker for update quick link not found")
text = replace_block(text, "export function useUpdateQuickLinkMutation", "export function useUpdateQuickLinkMutation() {\n  const queryClient = useQueryClient();\n  return useMutation<QuickLink, ApiError, { linkId: number | string; payload: UpdateQuickLinkInput }>({\n    mutationFn: async ({ linkId, payload }) =>\n      apiClient.patch<QuickLink>(endpoints.crawlers.quickLinks.byId(linkId), payload),\n    onSuccess: async () => {\n      await queryClient.invalidateQueries({ queryKey: quickLinkKeys.all });\n    },\n  });\n}\n\n")

if "export function useDeleteQuickLinkMutation" not in text:
  raise SystemExit("marker for delete quick link not found")
text = text.replace(
  "export function useDeleteQuickLinkMutation(linkId: number | string) {",
  "export function useDeleteQuickLinkMutation() {",
  1,
)
text = text.replace(
  "return useMutation<{ ok: boolean }, ApiError>({",
  "return useMutation<{ ok: boolean }, ApiError, number | string>({",
  1,
)
text = text.replace(
  "mutationFn: async () => apiClient.delete(endpoints.crawlers.quickLinks.byId(linkId))",
  "mutationFn: async (linkId) => apiClient.delete(endpoints.crawlers.quickLinks.byId(linkId))",
  1,
)

path.write_text(text, encoding="utf-8")
