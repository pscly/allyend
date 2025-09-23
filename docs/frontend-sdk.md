# 前端 SDK 使用指南（apiClient）

本指南介绍前端 `apiClient` 的使用方式、端点导航与最佳实践。

—

## 代码位置

- 客户端实现：`frontend/src/lib/api/client.ts`
- 端点定义：`frontend/src/lib/api/endpoints.ts`
- 类型定义：`frontend/src/lib/api/types.ts`
- 环境变量&URL 构建：`frontend/src/lib/env.ts`

## 设计原则

- 统一封装 `fetch`：提供 `get/post/patch/put/delete`，默认 `credentials: "include"`、`cache: "no-store"`。
- Cookie 会话：不再附加 `Authorization` 头部，登录后通过 Cookie 维持会话。
- 错误模型：服务端异常统一抛出 `ApiError`（含 `status`、`payload.detail/message`）。
- 响应解析：`204 No Content` 返回 `null`；`application/json` 自动解析为泛型类型。

## 环境变量

- `NEXT_PUBLIC_API_BASE_URL`：后端 API 基础地址。
  - 开发常用：`http://localhost:9093`
  - 生产（经反代）：设置为 `/api`（由 Nginx/Caddy 反向代理到后端）。
- `NEXT_PUBLIC_APP_BASE_URL`：前端站点地址（部分展示链接会使用）。

`buildApiUrl(path)` 会把上述基础地址与传入路径拼接：`apiBaseUrl + path`。

## 基础用法

```ts
import { apiClient } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { UserProfile } from "@/lib/api/types";

// 登录（Cookie 会话），随后再取个人资料
await apiClient.post(endpoints.auth.login, { username: "u", password: "p" });
const me = await apiClient.get<UserProfile>(endpoints.auth.profile);
```

### 方法签名与选项

- `get<T>(path, options?)`
- `post<T, TBody>(path, body?, options?)`
- `patch<T, TBody>(path, body?, options?)`
- `put<T, TBody>(path, body?, options?)`
- `delete<T>(path, options?)`

请求选项（`RequestOptions<TBody>`）：
- `body?: TBody | FormData`：JSON 或 `FormData`；为 JSON 时自动加 `Content-Type: application/json`。
- `searchParams?: Record<string, string | number | boolean | undefined>`：追加查询参数。
- `init?: RequestInit`：透传 `fetch` 原生配置（如 `signal`、`headers`）。

错误处理：

```ts
import { ApiError } from "@/lib/api/client";

try {
  const data = await apiClient.get<any>("/some/path");
} catch (e) {
  if (e instanceof ApiError) {
    console.error(e.status, e.payload?.detail || e.message);
  } else {
    console.error("网络/未知错误", e);
  }
}
```

## 端点导航（节选）

详见 `frontend/src/lib/api/endpoints.ts`。

- `auth`: 登录/注册/个人资料
- `files`: 我的文件列表、上传、删除、更新、下载、令牌、审计日志
- `crawlers`: 爬虫列表/详情、运行、日志、心跳、指令（创建/拉取/回执）、分组、配置模板/分配、告警、快捷链接
- `apiKeys`: API Key 的增删改查与轮转、公钥列表
- `admin`: 用户、邀请、分组、系统设置/注册模式
- `dashboard`: 概览、主题、活动流、公共页

## 常见场景示例

### 1) 登录与获取个人资料

```ts
import { apiClient } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { UserProfile } from "@/lib/api/types";

await apiClient.post(endpoints.auth.login, { username: "alice", password: "secret" });
const me = await apiClient.get<UserProfile>(endpoints.auth.profile);
```

### 2) 文件上传/列表/删除

```ts
import type { FileEntry } from "@/lib/api/types";

// 列表
const files = await apiClient.get<FileEntry[]>(endpoints.files.listMine);

// 上传（FormData）
const fd = new FormData();
fd.append("file", fileInput.files![0]);
fd.append("description", "说明可选");
await apiClient.post(endpoints.files.uploadMine, fd);

// 删除
await apiClient.delete(endpoints.files.deleteFile(123));
```

### 3) 爬虫：指令下发与回执

```ts
import type { CrawlerCommand } from "@/lib/api/types";

// 列出某爬虫的指令（或拉取下一批待处理指令）
const cmds = await apiClient.get<CrawlerCommand[]>(endpoints.crawlers.commands.list(1));
const next = await apiClient.post<CrawlerCommand[]>(endpoints.crawlers.commands.fetch(1));

// 回执某条指令
await apiClient.post(
  endpoints.crawlers.commands.ack(1, 99),
  { status: "success", result: { ok: true } },
);
```

### 4) 配置模板与分配

```ts
import type { CrawlerConfigTemplate, CrawlerConfigAssignment } from "@/lib/api/types";

// 模板列表/创建
const templates = await apiClient.get<CrawlerConfigTemplate[]>(endpoints.crawlers.config.templates.list);
const created = await apiClient.post<CrawlerConfigTemplate>(
  endpoints.crawlers.config.templates.create,
  { name: "基础模板", format: "json", content: "{\"a\":1}" },
);

// 分配列表/创建
const assigns = await apiClient.get<CrawlerConfigAssignment[]>(endpoints.crawlers.config.assignments.list);
await apiClient.post<CrawlerConfigAssignment>(endpoints.crawlers.config.assignments.create, {
  name: "news 配置",
  target_type: "crawler",
  target_id: 1,
  format: "json",
  content: "{\"interval\":5}",
});
```

### 5) React Query 集成（示例）

```ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { CrawlerGroup } from "@/lib/api/types";

export function useCrawlerGroups() {
  return useQuery({
    queryKey: ["crawler-groups"],
    queryFn: async () => apiClient.get<CrawlerGroup[]>(endpoints.crawlers.groups.list),
  });
}

export function useDeleteFile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => apiClient.delete(endpoints.files.deleteFile(id)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["my-files"] }),
  });
}
```

## 常见问题与最佳实践

- 会话与跨域：
  - 客户端默认 `credentials: "include"`；若前后端不同域，需确保后端 Cookie 设置 `SameSite=None` 且 `Secure=true`，并开启 HTTPS。
  - 生产建议把 `NEXT_PUBLIC_API_BASE_URL` 设为 `/api`，由网关/反代统一跨域与鉴权策略。
- JSON vs FormData：
  - 传 `FormData` 时，SDK 不设置 `Content-Type`（浏览器会自动带上 multipart 边界）。
  - 传对象时自动 `application/json` 并 `JSON.stringify`。
- 204 响应：返回 `null` 是预期行为（如删除成功等无响应体场景）。
- 超时与取消：通过 `options.init.signal` 传入 `AbortController.signal` 支持取消；如需全局超时，可在外层封装。
- 错误提示：捕获 `ApiError` 并优先显示 `payload.detail` 或 `payload.message`。

—

如需扩展端点或类型，请优先更新：`endpoints.ts` 与 `types.ts`，并在对应 Feature 下补充 `queries.ts`/`mutations.ts` 的调用封装。

