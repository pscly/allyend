import type { Page, APIRequestContext } from "@playwright/test";

type AuthResult = { ok: true } | { ok: false; reason: string };

async function setToken(page: Page, token: string): Promise<void> {
  // 与 zustand persist 对应的本地存储结构
  const persisted = JSON.stringify({ state: { token, profile: null }, version: 1 });
  await page.addInitScript(([k, v]) => {
    try {
      window.localStorage.setItem(k, v);
    } catch {}
  }, ["allyend-auth", persisted]);
}

export async function ensureAuth(page: Page, request: APIRequestContext): Promise<AuthResult> {
  const directToken = process.env.E2E_TOKEN;
  const user = process.env.E2E_USERNAME;
  const pass = process.env.E2E_PASSWORD;

  if (directToken && directToken.trim()) {
    await setToken(page, directToken.trim());
    return { ok: true };
  }

  if (user && pass) {
    try {
      const resp = await request.post("/api/auth/login", {
        data: { username: user, password: pass },
      });
      if (!resp.ok()) {
        return { ok: false, reason: `login failed: ${resp.status()} ${resp.statusText()}` };
      }
      const json = (await resp.json()) as { access_token?: string };
      const token = json?.access_token;
      if (!token) return { ok: false, reason: "no token in response" };
      await setToken(page, token);
      return { ok: true };
    } catch (e) {
      return { ok: false, reason: String(e) };
    }
  }

  return { ok: false, reason: "E2E_TOKEN or E2E_USERNAME/PASSWORD not provided" };
}

