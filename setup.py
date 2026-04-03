import os, sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'z_padel'))
if not os.path.exists(os.path.join(BASE, 'run.py')):
    # Try current directory
    BASE = os.path.abspath('.')

print(f"Project root: {BASE}")

OUTPUTS = os.path.dirname(os.path.abspath(__file__))

FILES = {
    'base_admin.html':        'app/templates/admin/base_admin.html',
    'dashboard.html':         'app/templates/admin/dashboard.html',
    'bookings.html':          'app/templates/admin/bookings.html',
    'pending_bookings.html':  'app/templates/admin/pending_bookings.html',
    'products.html':          'app/templates/admin/products.html',
    'reports.html':           'app/templates/admin/reports.html',
    'expenses.html':          'app/templates/admin/expenses.html',
    'orders.html':            'app/templates/admin/orders.html',
    'courts.html':            'app/templates/admin/courts.html',
    'settings.html':          'app/templates/admin/settings.html',
    'users.html':             'app/templates/admin/users.html',
    'login.html':             'app/templates/auth/login.html',
    '__init__.py':            'app/__init__.py',
    'models__init__.py':      'app/models/__init__.py',
    'models_main.py':         'app/models/main.py',
    'models_store.py':        'app/models/store.py',
    'auth.py':                'app/routes/auth.py',
    'main.py':                'app/routes/main.py',
    'admin.py':               'app/routes/admin.py',
    'booking.py':             'app/routes/booking.py',
    'store.py':               'app/routes/store.py',
    'pos.py':                 'app/routes/pos.py',
    'config.py':              'config.py',
    'run.py':                 'run.py',
}

ok = 0
skip = 0
for src_name, dst_rel in FILES.items():
    src = os.path.join(OUTPUTS, src_name)
    dst = os.path.join(BASE, dst_rel.replace('/', os.sep))
    if not os.path.exists(src):
        print(f"  SKIP  {src_name}")
        skip += 1
        continue
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(src, 'r', encoding='utf-8') as f:
        content = f.read()
    with open(dst, 'w', encoding='utf-8') as f:
        f.write(content)
    size = os.path.getsize(dst)
    print(f"  OK    {dst_rel} ({size:,} bytes)")
    ok += 1

print(f"\n✅  {ok} files installed, {skip} skipped.")
print("Now run: python run.py")
