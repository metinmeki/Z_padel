path = "app/templates/admin/products.html"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

old = "images/products/"
new = "images/uploads/"

count = content.count(old)
content = content.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print(f"Replaced {count} occurrence(s) in {path}")
