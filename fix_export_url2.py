path = "app/templates/admin/bookings.html"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

old = "url_for('admin.bookings', export='csv', **{k: v for k, v in request.args.items() if k != 'export'})"
new = "url_for('admin.bookings', export='csv')"

if old in content:
    content = content.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Patched successfully")
else:
    print("Pattern not found - printing context")
    idx = content.find("export=")
    print(repr(content[idx-40:idx+120]))
