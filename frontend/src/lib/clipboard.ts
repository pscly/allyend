// 剪贴板工具：在不支持或非安全上下文下提供降级复制方案
// 说明：优先使用 Clipboard API；若不可用，则回退到隐藏文本域 + execCommand('copy')

export async function copyToClipboard(text: string): Promise<boolean> {
  // SSR 环境直接失败
  if (typeof window === "undefined") return false;

  try {
    if (typeof navigator !== "undefined" && navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // 忽略，转入降级方案
  }

  try {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    textarea.style.pointerEvents = "none";
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(textarea);
    return ok;
  } catch {
    return false;
  }
}

