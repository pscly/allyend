import type { APIRequestContext } from "@playwright/test";

type AuthResult = { ok: true } | { ok: false; reason: string };

export async function ensureAuth(_page: unknown, request: APIRequestContext): Promise<AuthResult> {
  const user = process.env.E2E_USERNAME;
  const pass = process.env.E2E_PASSWORD;

  if (user && pass) {
    try {
      const resp = await request.post("/api/auth/login", {
        data: { username: user, password: pass },
      });
      if (!resp.ok()) {
        return { ok: false, reason: `login failed: ${resp.status()} ${resp.statusText()}` };
      }
      // 登录成功后，Cookie 已写入上下文；页面请求将自动携带
      return { ok: true };
    } catch (e) {
      return { ok: false, reason: String(e) };
    }
  }

  return { ok: false, reason: "E2E_USERNAME/PASSWORD not provided" };
}
