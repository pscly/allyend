import { test, expect } from "@playwright/test";
import { ensureAuth } from "./helpers/auth";

test.describe("Crawlers · Key 管理", () => {
test("创建并编辑 Key", async ({ page, request }) => {
    const baseURL = test.info().project.use.baseURL as string | undefined;
    if (!baseURL) test.skip();

    const auth = await ensureAuth(page, request);
    if (!auth.ok) test.skip();

    const keyName = `e2e-key-${Date.now()}`;
    const keyNameUpdated = `${keyName}-upd`;

    await page.goto("/dashboard/crawlers");
    await expect(page.getByRole("heading", { name: "爬虫控制台" })).toBeVisible();

    // 切到 Key 管理页签
    await page.getByRole("tab", { name: "Key 管理" }).click();

    // 打开“新建 Key”对话框
    await page.getByRole("button", { name: /新建 Key/ }).click();

    // 填写表单并提交
    await page.getByLabel("名称").fill(keyName);
    await page.getByLabel("描述").fill("e2e 自动化创建");
    await page.getByRole("button", { name: "确认创建" }).click();

    // 断言创建成功提示
    await expect(page.getByText("Key 已创建")).toBeVisible();

    // 表格中能看到新建的 Key 名称
    await expect(page.getByRole("row", { name: new RegExp(keyName) })).toBeVisible();

    // 行内打开更多菜单并点击编辑
    const row = page.getByRole("row", { name: new RegExp(keyName) });
    await row.locator("td:last-child button").first().click();
    await page.getByRole("menuitem", { name: "编辑" }).click();

    // 编辑名称并保存
    await page.getByRole("dialog").getByLabel("名称").fill(keyNameUpdated);
    await page.getByRole("button", { name: "保存" }).click();

    await expect(page.getByText("Key 已更新")).toBeVisible();
    await expect(page.getByRole("row", { name: new RegExp(keyNameUpdated) })).toBeVisible();
  });
});
