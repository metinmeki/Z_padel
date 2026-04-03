from flask import Blueprint, render_template, redirect, url_for, request, flash
from datetime import datetime, date
from app import db
from app.models.main import Court, Booking

booking_bp = Blueprint('booking', __name__)


@booking_bp.route('/')
def index():
    courts = Court.query.filter_by(is_active=True).all()
    today  = date.today().isoformat()

    # Convert courts to JSON-serializable list
    courts_data = []
    for c in courts:
        courts_data.append({
            'id':             c.id,
            'name':           c.name,
            'price_per_hour': c.price_per_hour or 25000,
            'color':          c.color or '#1565C0',
        })

    # Build booked slots dict: {"court_id:date": ["HH:MM", ...]}
    booked_slots = {}
    bookings = Booking.query.filter(Booking.status != 'cancelled').all()
    for b in bookings:
        key = f"{b.court_id}:{b.booking_date.isoformat()}"
        if key not in booked_slots:
            booked_slots[key] = []
        if b.start_time:
            booked_slots[key].append(b.start_time.strftime('%H:%M'))

    return render_template('booking.html',
        courts=courts,
        courts_data=courts_data,
        today=today,
        booked_slots=booked_slots,
    )


@booking_bp.route('/create', methods=['POST'])
def create():
    try:
        court  = Court.query.get_or_404(request.form['court_id'])
        b_date = datetime.strptime(request.form['booking_date'], '%Y-%m-%d').date()
        s_time = datetime.strptime(request.form['start_time'], '%H:%M').time()
        e_time = datetime.strptime(request.form['end_time'],   '%H:%M').time()

        bk = Booking(
            court_id=court.id,
            customer_name=request.form['customer_name'],
            customer_phone=request.form['customer_phone'],
            booking_date=b_date,
            start_time=s_time,
            end_time=e_time,
            status='pending',
            notes=request.form.get('notes', ''),
        )
        bk.total_price = bk.calc_price(court.price_per_hour)
        db.session.add(bk)
        db.session.commit()
        flash('تم استلام طلب حجزك بنجاح! سيتم التأكيد قريباً.', 'success')
        return redirect(url_for('booking.success', booking_id=bk.id))
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ: {e}', 'danger')
        return redirect(url_for('booking.index'))


@booking_bp.route('/success/<int:booking_id>')
def success(booking_id):
    bk = Booking.query.get_or_404(booking_id)
    return render_template('booking_success.html', booking=bk)