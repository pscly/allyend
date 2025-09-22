import { beforeEach, describe, expect, it } from "vitest";

import type { UserProfile } from "@/lib/api/types";
import { logout, useAuthStore } from "@/store/auth-store";

describe("auth-store", () => {
  beforeEach(() => {
    useAuthStore.setState({ profile: null, hydrated: true });
    if (typeof window !== "undefined") {
      window.localStorage?.clear?.();
    }
  });

  it("setProfile 会保存用户资料", () => {
    const profile: UserProfile = {
      id: 1,
      username: "tester",
      display_name: "测试用户",
      email: null,
      role: "user",
      is_active: true,
    };
    useAuthStore.getState().setProfile(profile);
    const state = useAuthStore.getState();
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
    useAuthStore.setState({ profile, hydrated: true });
    logout();
    const state = useAuthStore.getState();
    expect(state.profile).toBeNull();
    expect(state.hydrated).toBe(true);
  });
});
