from app import create_app, db
from app.models.store import Product
import os

app = create_app()
with app.app_context():
    products = Product.query.filter(Product.image.isnot(None)).all()
    fixed = []
    for p in products:
        path = os.path.join("app", "static", "images", "products", p.image)
        if not os.path.exists(path):
            print(f"Clearing broken image for: {p.name} (was: {p.image})")
            p.image = None
            fixed.append(p.name)
    if fixed:
        db.session.commit()
        print(f"\nFixed {len(fixed)} product(s): {fixed}")
    else:
        print("No broken images found.")
