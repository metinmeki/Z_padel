path = "app/templates/pos/session_detail.html"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

old = "  .invoice-panel { position: sticky; top: 76px; }"
new = "  .invoice-panel { position: static; }\n  @media (min-width: 992px) {\n    .invoice-panel { position: sticky; top: 76px; }\n  }"

if old in content:
    content = content.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Patched: sticky invoice panel now desktop-only")
else:
    print("Pattern not found - printing context")
    idx = content.find("invoice-panel")
    print(repr(content[idx-5:idx+120]))
