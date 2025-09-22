import { test, expect, request } from "@playwright/test";

const API = process.env.PLAYWRIGHT_API_BASE_URL || "http://localhost:9093";

test.describe("后端 API 冒烟", () => {
  test("登录后创建 Key 并查询用户/Key 列表", async () => {
    const ctx = await request.newContext({ baseURL: API });

    // 1) 登录，保存 Cookie 会话
    const loginRes = await ctx.post("/api/auth/login", {
      data: { username: "root", password: "please_change_me" },
    });
    expect(loginRes.ok()).toBeTruthy();

    // 2) 创建 Key
    const createRes = await ctx.post("/api/keys", {
      data: { name: "api-e2e", description: "playwright" },
    });
    expect(createRes.ok()).toBeTruthy();

    // 3) 列出 Key，应至少 1 条
    const listRes = await ctx.get("/api/keys");
    expect(listRes.ok()).toBeTruthy();
    const keys = (await listRes.json()) as Array<any>;
    expect(Array.isArray(keys) && keys.length > 0).toBeTruthy();

    // 4) 管理员用户列表，应包含 root（根管理员）
    const usersRes = await ctx.get("/admin/api/users");
    expect(usersRes.ok()).toBeTruthy();
    const users = (await usersRes.json()) as Array<any>;
    const hasRoot = users.some((u) => u.username === "root");
    expect(hasRoot).toBeTruthy();
  });
});

