from pathlib import Path
path = Path("frontend/src/app/(protected)/dashboard/crawlers/page.tsx")
text = path.read_text(encoding="utf-8")
start = text.index("  const commandForm")
print(repr(text[start:start+60]))
