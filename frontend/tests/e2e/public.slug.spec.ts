import { test, expect } from "@playwright/test";

test.describe("公开页直达验证", () => {
  test("/pa/bu1i-kbq 可访问并返回 200", async ({ page }) => {
    const resp = await page.goto("/pa/bu1i-kbq");
    expect(resp?.ok()).toBeTruthy();
    // 后端模板包含“访问路径：/pa/<slug>”提示
    await expect(page.getByText("访问路径")).toBeVisible();
  });
});

