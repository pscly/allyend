import { beforeEach, describe, expect, it } from "vitest";

import type { TokenResponse, UserProfile } from "@/lib/api/types";
import { logout, persistToken, useAuthStore } from "@/store/auth-store";

describe("auth-store", () => {
  beforeEach(() => {
    useAuthStore.setState({ token: null, profile: null, hydrated: true });
    if (typeof window !== "undefined") {
      window.localStorage?.clear?.();
    }
  });

  it("persistToken 会保存访问令牌", () => {
    const token: TokenResponse = { access_token: "abc123", token_type: "bearer" };
    persistToken(token);
    const state = useAuthStore.getState();
    expect(state.token).toBe("abc123");
    expect(state.profile).toBeNull();
    expect(state.hydrated).toBe(true);
  });

  it("persistToken 支持同步用户资料", () => {
    const token: TokenResponse = { access_token: "abc456", token_type: "bearer" };
    const profile: UserProfile = {
      id: 1,
      username: "tester",
      display_name: "测试用户",
      email: null,
      role: "user",
      is_active: true,
    };
    persistToken(token, profile);
    const state = useAuthStore.getState();
    expect(state.token).toBe("abc456");
    expect(state.profile?.username).toBe("tester");
    expect(state.hydrated).toBe(true);
  });

  it("logout 会清空 token 与 profile", () => {
    const profile: UserProfile = {
      id: 1,
      username: "tester",
      display_name: null,
      email: null,
      role: "user",
      is_active: true,
    };
    useAuthStore.setState({ token: "abc", profile, hydrated: true });
    logout();
    const state = useAuthStore.getState();
    expect(state.token).toBeNull();
    expect(state.profile).toBeNull();
    expect(state.hydrated).toBe(true);
  });
});
