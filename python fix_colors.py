file = 'app/templates/admin/dashboard.html'

with open(file, 'r', encoding='utf-8') as f:
    content = f.read()

replacements = [
    ('var(--brand-blue-deep)', 'var(--brand-deep)'),
    ('var(--brand-blue-dark)', 'var(--brand-dark)'),
    ('var(--brand-blue-light)', 'var(--brand-light)'),
    ('var(--brand-blue-soft)', 'var(--brand-soft)'),
    ('var(--brand-blue-mid)', 'var(--brand-mid)'),
    ('var(--brand-blue)', 'var(--brand)'),
    ('rgba(21,101,192', 'rgba(89,103,112'),
    ('rgba(0,176,255', 'rgba(214,195,161'),
    ("'#1565C0'", "'#596770'"),
    ("'#00B0FF'", "'#D6C3A1'"),
    ("color: '#0D1B3E'", "color: '#2C3539'"),
    ("color: '#6B8BB5'", "color: '#7A8A93'"),
    ('#1565C0', '#596770'),
    ('#00B0FF', '#D6C3A1'),
    ('#0D1B3E', '#2C3539'),
    ('#6B8BB5', '#7A8A93'),
    ('#BBDEFB', '#E8DFD0'),
    ('#E3F0FF', '#F5F2ED'),
]

for old, new in replacements:
    content = content.replace(old, new)

with open(file, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done! All colors updated.')