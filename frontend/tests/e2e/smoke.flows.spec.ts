import { test, expect } from "@playwright/test";

// 端到端冒烟：登录 -> 创建 Key -> 刷新后仍可见 -> 管理页可见用户
test.describe("端到端冒烟", () => {
  test("登录、创建 Key 并验证持久化；管理页可见用户", async ({ page }) => {
    // 1) 登录
    await page.goto("/login");
    await page.getByLabel("用户名").fill("root");
    await page.getByLabel("密码").fill("please_change_me");
    await page.getByRole("button", { name: "登录" }).click();
    await page.waitForURL(/\/dashboard(\/.*)?$/);

    // 2) 打开爬虫页面并创建 Key
    await page.goto("/dashboard/crawlers");
    await page.getByRole("button", { name: "新建 Key" }).click();
    await page.getByLabel("名称").fill("e2e-key");
    await page.getByRole("button", { name: "确认创建" }).click();

    // 创建成功后应出现“已生成新的 Key”提示区块
    await expect(page.getByText("已生成新的 Key")).toBeVisible();

    // 关闭弹窗并刷新
    await page.getByRole("button", { name: "取消" }).click();
    await page.reload();

    // 刷新后 Key 列表中应能看到至少一条记录（包含“启用”字样或“API Key 管理”表格内容）
    await expect(page.getByText("API Key 管理")).toBeVisible();
    // 简单判断：页面上应出现“启用”或“未命名/名称列”之一
    const hasEnabled = await page.getByText("启用").first().isVisible().catch(() => false);
    const hasRow = await page.getByRole("cell", { name: /未命名|e2e-key/ }).first().isVisible().catch(() => false);
    expect(hasEnabled || hasRow).toBeTruthy();

    // 3) 管理页应能看到用户列表（root）
    await page.goto("/admin");
    await expect(page.getByText("后台管理控制中心")).toBeVisible();
    await expect(page.getByText("成员管理")).toBeVisible();
    await expect(page.getByText("root")).toBeVisible();
  });
});

