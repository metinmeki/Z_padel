from flask import Blueprint, render_template
from app.models.main import Court, Booking

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    courts = Court.query.filter_by(is_active=True).all()
    total_bookings = Booking.query.filter_by(status='confirmed').count()
    return render_template('index.html', courts=courts, total_bookings=total_bookings)