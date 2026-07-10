files = [
    "app/templates/pos/quick_sale.html",
    "app/templates/pos/session_detail.html",
]

old = "images/products/"
new = "images/uploads/"

for path in files:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    count = content.count(old)
    content = content.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"{path}: replaced {count} occurrence(s)")
