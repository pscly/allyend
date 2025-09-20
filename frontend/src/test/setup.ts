import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// 每次测试后自动清理挂载的 React 组件，避免测试间相互影响
afterEach(() => {
  cleanup();
});
