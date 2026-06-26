from flask import Blueprint, render_template, session, redirect, request
from app.models.main import Court, Booking, Coach
from app.models.store import Product  # Import at the top

main_bp = Blueprint('main', __name__)


@main_bp.route('/set-lang/<lang>')
def set_lang(lang):
    if lang in ('ar', 'en'):
        session['lang'] = lang
        session.permanent = True
    return redirect(request.referrer or '/')


@main_bp.route('/')
def loading():
    return render_template('loading.html')


@main_bp.route('/home')
def index():
    # Fetch all data needed for the index.html page
    coaches = Coach.query.filter_by(is_active=True).all()
    courts = Court.query.filter_by(is_active=True).all()
    total_bookings = Booking.query.filter_by(status='confirmed').count()

    # Fetch active products marked for the website, limited to 4
    products = Product.query.filter_by(is_active=True, show_on_website=True).limit(4).all()

    return render_template('index.html',
                           coaches=coaches,
                           courts=courts,
                           total_bookings=total_bookings,
                           products=products)
@main_bp.route('/sw.js')
def sw():
    from flask import send_from_directory, current_app
    return send_from_directory(current_app.static_folder, 'sw.js'), 200, {'Content-Type': 'application/javascript'}
