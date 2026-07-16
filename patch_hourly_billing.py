import re

PATH = "app/models/main.py"

OLD = """    def calc_price(self):
        hours = self.elapsed_minutes / 60
        rate = self.court.price_per_hour if self.court else 40000
        return round(hours * rate)"""

NEW = """    def calc_price(self):
        import math
        hours_billed = max(1, math.ceil(self.elapsed_minutes / 60))
        rate = self.court.price_per_hour if self.court else 40000
        return round(hours_billed * rate)"""

with open(PATH, "r", encoding="utf-8") as f:
    content = f.read()

if NEW.split("\n")[1] in content:
    print("Already patched - no changes made.")
elif OLD not in content:
    print("ERROR: could not find the exact calc_price() block to replace.")
    idx = content.find("def calc_price")
    print(repr(content[idx-10:idx+250]))
else:
    content = content.replace(OLD, NEW)
    with open(PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print("Patched successfully: calc_price() now bills full hours, minimum 1 hour.")
