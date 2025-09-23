# AllYend 前端（Next.js 14）

该目录提供基于 Next.js 14 + React 18.3 的全新前端实现，配合后端 FastAPI 构成前后端分离方案。

## 快速开始

```bash
pnpm install
pnpm dev
```

开发默认使用 Node.js 22.x，请确保本地使用 `scoop install nodejs-lts` 或 `nvm use 22` 切换版本。

## 主要依赖

- Next.js 14 (App Router)
- React 18.3 + TypeScript 5
- Tailwind CSS 3.4 + shadcn/ui 组件集
- @tanstack/react-query 处理数据缓存
- react-hook-form + zod 管理表单与校验
- zustand 负责全局轻量状态

## 目录结构

```
frontend/
├── src/
│   ├── app/               # Next App Router 页面
│   ├── components/        # UI 组件与布局、Provider
│   ├── lib/               # API 客户端、工具方法
│   ├── store/             # zustand 状态仓库
│   ├── hooks/             # 公共 hook
│   └── ui/                # shadcn 生成的基础组件
└── .husky/                # 提交钩子（与 lint-staged 联动）
```

## 常用脚本

```bash
pnpm dev          # 本地开发（Turbopack）
pnpm build        # 生产构建
pnpm lint         # 组合执行 ESLint + Stylelint
pnpm format       # Prettier 全量格式化
pnpm test         # Vitest（后续补充）
pnpm test:ui      # Playwright（后续补充）
```

## 环境变量

| 变量名 | 说明 | 默认值 |
| ------ | ---- | ------ |
| `NEXT_PUBLIC_API_BASE_URL` | 后端 FastAPI 访问地址 | `/api` |
| `NEXT_PUBLIC_APP_BASE_URL` | 当前前端地址（用于拼接站点链接） | `http://localhost:8080` |

复制 `.env.example` 即可开始本地调试。

## 前端 SDK（apiClient）

- 位置：`src/lib/api/client.ts`（客户端）、`src/lib/api/endpoints.ts`（端点）、`src/lib/api/types.ts`（类型）
- 会话：默认使用 Cookie（`credentials: include`），不附加 `Authorization` 头
- 环境：`NEXT_PUBLIC_API_BASE_URL` 指向后端（开发常用 `http://localhost:9093`，生产经反代建议 `/api`）

快速示例：

```ts
import { apiClient } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { UserProfile } from "@/lib/api/types";

await apiClient.post(endpoints.auth.login, { username: "u", password: "p" });
const me = await apiClient.get<UserProfile>(endpoints.auth.profile);
```

常见问题与更完整示例（文件上传/指令回执/React Query 集成等）请查看：`docs/frontend-sdk.md`。

## 代码规范

- ESLint 9 + @typescript-eslint 保障语法质量
- Stylelint 16 + Tailwind 插件约束样式
- Prettier 3（集成 Tailwind 排序插件）
- lint-staged + Husky 在提交前自动执行检查

## 后续工作指引

- Step 2 当前为骨架页面，尚未接入真实 API
- Step 3 将补充登录、文件、爬虫、管理等页面的数据逻辑
- Step 4 会落地 Vitest/Playwright 测试与 CI 脚本

