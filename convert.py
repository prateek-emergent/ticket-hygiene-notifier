import json, sys
src, out = sys.argv[1], sys.argv[2]
with open(src, encoding="utf-8") as f, open(out, "w", encoding="utf-8") as o:
    for line in f:
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = e.get("message")
        if not msg or e.get("type") not in ("user", "assistant"):
            continue
        content = msg.get("content")
        if isinstance(content, list):
            content = "\n".join(c.get("text", "") for c in content if c.get("type") == "text")
        if content and content.strip():
            o.write(f"## {msg['role'].title()}\n\n{content}\n\n---\n\n")
