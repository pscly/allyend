import { test } from "@playwright/test";

// TODO: 待后端与前端联机后补充真实的端到端流程
// 目前使用 skip 保留测试结构，避免流水线阻塞。
test.describe.skip("认证流程", () => {
  test("登录后可访问控制台", async ({ page }) => {
    await page.goto("/");
  });
});
