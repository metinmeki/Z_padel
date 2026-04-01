# ══════════════════════════════════════════════════════════════
#  migrate.py  —  شغّله مرة واحدة لإضافة الأعمدة الجديدة
#  ضعه في جذر المشروع (نفس مكان run.py) وشغّله:
#  python migrate.py
# ══════════════════════════════════════════════════════════════

from app import create_app, db
import sqlalchemy as sa

app = create_app()

with app.app_context():
    with db.engine.connect() as conn:

        # ── Add show_on_website to product ──
        try:
            conn.execute(sa.text(
                "ALTER TABLE product ADD COLUMN show_on_website BOOLEAN DEFAULT 0"
            ))
            conn.commit()
            print("✅ Added: product.show_on_website")
        except Exception as e:
            print(f"⚠️  product.show_on_website: {e}")

        # ── Add source to order ──
        try:
            conn.execute(sa.text(
                "ALTER TABLE `order` ADD COLUMN source VARCHAR(20) DEFAULT 'website'"
            ))
            conn.commit()
            print("✅ Added: order.source")
        except Exception as e:
            print(f"⚠️  order.source: {e}")

    print("\n✅ Migration complete!")