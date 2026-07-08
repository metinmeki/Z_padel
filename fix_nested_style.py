FILES = [
    "app/templates/pos/courts.html",
    "app/templates/pos/session_detail.html",
]

for path in FILES:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    original = content

    # Handle both \n and \r\n line endings
    content = content.replace("{% block extra_css %}\r\n<style>\r\n", "{% block extra_css %}\r\n")
    content = content.replace("{% block extra_css %}\n<style>\n", "{% block extra_css %}\n")

    content = content.replace("</style>\r\n{% endblock %}", "{% endblock %}")
    content = content.replace("</style>\n{% endblock %}", "{% endblock %}")

    if content == original:
        print(f"{path}: STILL no changes - showing context for manual check")
        idx = content.find("{% block extra_css %}")
        print(repr(content[idx:idx+60]))
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"{path}: patched successfully")
