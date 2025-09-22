import { test, expect } from "@playwright/test";
import { ensureAuth } from "./helpers/auth";

test.describe("Crawlers · 公开页面", () => {
test("为 API Key 创建公开页", async ({ page, request }) => {
    const baseURL = test.info().project.use.baseURL as string | undefined;
    if (!baseURL) test.skip();

    const auth = await ensureAuth(page, request);
    if (!auth.ok) test.skip();

    const keyName = `e2e-key-${Date.now()}`;

    // 先创建一个 Key，后续用于公开页
    await page.goto("/dashboard/crawlers");
    await page.getByRole("tab", { name: "Key 管理" }).click();
    await page.getByRole("button", { name: /新建 Key/ }).click();
    await page.getByLabel("名称").fill(keyName);
    await page.getByRole("button", { name: "确认创建" }).click();
    await expect(page.getByText("Key 已创建")).toBeVisible();

    // 切换到公开页面页签
    await page.getByRole("tab", { name: "公开页面" }).click();
    await page.getByRole("button", { name: "创建公开页" }).click();

    // 选择目标类型与目标对象
    await page.getByLabel("目标类型").selectOption("api_key");
    await page.getByLabel("目标").selectOption({ label: keyName });

    // 提交创建
    await page.getByRole("button", { name: "确认创建" }).click();
    await expect(page.getByText("公开页已创建")).toBeVisible();

    // 列表中应可见一个 /pa/ 链接（不强依赖具体 slug 文本）
    await expect(page.locator('a[href^="/pa/"]').first()).toBeVisible();
  });
});
