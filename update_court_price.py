from app import create_app, db
from app.models.main import Court

app = create_app()
with app.app_context():
    courts = Court.query.all()
    for c in courts:
        print(f"{c.name}: {c.price_per_hour} -> 50000")
        c.price_per_hour = 50000
    db.session.commit()
    print(f"\nUpdated {len(courts)} court(s) to 50,000 IQD/hour")
