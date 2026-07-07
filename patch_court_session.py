"""
Patches app/models/main.py: adds items_total, time_amount, grand_total
properties to the CourtSession class, right after calc_price().
Run from project root: python patch_court_session.py
"""

PATH = "app/models/main.py"

MARKER = "    def calc_price(self):\n        hours = self.elapsed_minutes / 60\n        rate = self.court.price_per_hour if self.court else 40000\n        return round(hours * rate)\n"

ADDITION = """
    @property
    def items_total(self):
        return sum(i.subtotal for i in self.items) if self.items else 0

    @property
    def time_amount(self):
        if self.status == 'active' and not self.end_time:
            return self.calc_price()
        return self.total_price or 0

    @property
    def grand_total(self):
        return round(self.time_amount + self.items_total)
"""

with open(PATH, "r", encoding="utf-8") as f:
    content = f.read()

if "def grand_total" in content:
    print("grand_total already present — no changes made.")
elif MARKER not in content:
    print("ERROR: could not find calc_price() block to anchor the patch.")
    print("Please add the properties manually inside the CourtSession class.")
else:
    content = content.replace(MARKER, MARKER + ADDITION)
    with open(PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print("Patched successfully: items_total, time_amount, grand_total added.")