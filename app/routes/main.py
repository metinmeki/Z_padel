from flask import Blueprint, render_template
from app.models.main import Court, Booking, Coach

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def loading():
    return render_template('loading.html')


@main_bp.route('/home')
def index():
    coaches = Coach.query.filter_by(is_active=True).all()  # ✅ ADD THIS
    courts = Court.query.filter_by(is_active=True).all()
    total_bookings = Booking.query.filter_by(status='confirmed').count()
    return render_template('index.html', coaches=coaches, courts=courts, total_bookings=total_bookings)