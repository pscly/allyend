"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";

import { Button } from "@/components/ui/button";
import { copyToClipboard } from "@/lib/clipboard";

interface CopyTextButtonProps {
  value: string;
  label?: string;
}

export function CopyTextButton({ value, label = "复制" }: CopyTextButtonProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      const ok = await copyToClipboard(value);
      if (ok) {
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }
    } catch (error) {
      console.error("复制失败", error);
    }
  };

  return (
    <Button variant="outline" size="sm" onClick={handleCopy} aria-label={label}>
      {copied ? <Check className="mr-2 h-4 w-4" /> : <Copy className="mr-2 h-4 w-4" />}
      {copied ? "已复制" : label}
    </Button>
  );
}
