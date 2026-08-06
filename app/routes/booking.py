from flask import Blueprint, render_template, redirect, url_for, request, flash
from datetime import datetime, date, time as dtime
from app import db
from app.models.main import Court, Booking

def _parse_time(t):
    """Parse HH:MM, treating 24:00 as 23:59."""
    if t == '24:00':
        return dtime(23, 59)
    return datetime.strptime(t, '%H:%M').time()

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
        s_time = _parse_time(request.form['start_time'])
        e_time = _parse_time(request.form['end_time'])

        # Reject if another non-cancelled booking already occupies this slot
        conflict = Booking.query.filter(
            Booking.court_id    == court.id,
            Booking.booking_date == b_date,
            Booking.start_time   == s_time,
            Booking.status       != 'cancelled',
        ).first()
        if conflict:
            flash('عذراً، هذا الوقت محجوز بالفعل. يرجى اختيار وقت آخر.', 'danger')
            return redirect(url_for('booking.index'))

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