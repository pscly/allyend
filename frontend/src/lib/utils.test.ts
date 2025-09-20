import { describe, expect, it } from "vitest";

import { cn } from "./utils";

describe("cn", () => {
  it("合并不同格式的 className", () => {
    expect(cn("flex", undefined, null, "items-center"))
      .toBe("flex items-center");
  });

  it("自动去重尾随空格", () => {
    expect(cn("bg-white", "text-sm", "bg-white")).toBe("text-sm bg-white");
  });
});
