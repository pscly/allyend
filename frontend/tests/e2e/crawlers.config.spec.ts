import { test, expect } from "@playwright/test";
import { ensureAuth } from "./helpers/auth";

test.describe("Crawlers · 配置指派", () => {
test("创建配置指派（直接内容）", async ({ page, request }) => {
    const baseURL = test.info().project.use.baseURL as string | undefined;
    if (!baseURL) test.skip();

    const auth = await ensureAuth(page, request);
    if (!auth.ok) test.skip();

    const keyName = `e2e-key-${Date.now()}`;

    // 先创建一个 Key 作为目标
    await page.goto("/dashboard/crawlers");
    await page.getByRole("tab", { name: "Key 管理" }).click();
    await page.getByRole("button", { name: /新建 Key/ }).click();
    await page.getByLabel("名称").fill(keyName);
    await page.getByRole("button", { name: "确认创建" }).click();
    await expect(page.getByText("Key 已创建")).toBeVisible();

    // 切到“配置与告警”页签
    await page.getByRole("tab", { name: "配置与告警" }).click();

    // 在“配置指派”卡片内填写并创建
    await page.getByRole("form").filter({ hasText: "新建配置指派" }).getByLabel("名称").fill(`e2e-assign-${Date.now()}`);
    await page.getByRole("form").filter({ hasText: "新建配置指派" }).getByLabel("目标类型").selectOption("api_key");
    await page.getByRole("form").filter({ hasText: "新建配置指派" }).getByLabel("目标").selectOption({ label: keyName });
    await page.getByRole("form").filter({ hasText: "新建配置指派" }).getByLabel("配置内容（覆盖模板时填写）").fill('{"hello":"world"}');

    await page.getByRole("form").filter({ hasText: "新建配置指派" }).getByRole("button", { name: /创建指派|保存指派|保存中|创建中/ }).click();

    await expect(page.getByText("配置指派已创建")).toBeVisible();
  });
});
