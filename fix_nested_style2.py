path = "app/templates/pos/session_detail.html"

with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

fixed = []
skip_next_closing = False

for i, line in enumerate(lines):
    stripped = line.strip()
    if stripped == "{% block extra_css %}":
        fixed.append(line)
        continue
    if stripped == "<style>" and i > 0 and lines[i-1].strip() == "{% block extra_css %}":
        continue  # skip this line, do not include the stray <style>
    if stripped == "</style>" and i + 1 < len(lines) and lines[i+1].strip() == "{% endblock %}":
        continue  # skip this line, do not include the stray </style>
    fixed.append(line)

with open(path, "w", encoding="utf-8") as f:
    f.writelines(fixed)

print("Removed nested <style> wrapper from extra_css block")
