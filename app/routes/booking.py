from flask import Blueprint, render_template, redirect, url_for, request, flash
from datetime import datetime, date, time as dtime, timedelta
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

    # Build booked slots dict: {"court_id:date": ["HH:MM", ...]} covering every 30-min interval
    booked_slots = {}
    bookings = Booking.query.filter(Booking.status != 'cancelled').all()
    for b in bookings:
        if not b.start_time or not b.end_time:
            continue
        key = f"{b.court_id}:{b.booking_date.isoformat()}"
        if key not in booked_slots:
            booked_slots[key] = []
        start_m = b.start_time.hour * 60 + b.start_time.minute
        end_m   = b.end_time.hour   * 60 + b.end_time.minute
        if end_m < start_m:  # cross-midnight: extend end past 24h boundary
            end_m += 24 * 60
        next_key = None
        m = start_m
        while m < end_m:
            if m >= 24 * 60:
                # Post-midnight slots belong to the next calendar day
                if next_key is None:
                    next_date = b.booking_date + timedelta(days=1)
                    next_key = f"{b.court_id}:{next_date.isoformat()}"
                    if next_key not in booked_slots:
                        booked_slots[next_key] = []
                actual_m = m - 24 * 60
                ts = f"{actual_m//60:02d}:{actual_m%60:02d}"
                if ts not in booked_slots[next_key]:
                    booked_slots[next_key].append(ts)
            else:
                ts = f"{m//60:02d}:{m%60:02d}"
                if ts not in booked_slots[key]:
                    booked_slots[key].append(ts)
            m += 30

        # Early morning standalone bookings (00:00–08:00, not a cross-midnight bk2)
        # must also block the "bottom slots" of the previous day's booking page,
        # which checks the next_key of that day (= this booking's date key).
        # Additionally mirror into THIS date's next_key so today's bottom slots
        # correctly show them as blocked.
        if not getattr(b, 'is_continuation', False) and b.start_time.hour < 8:
            mirror_key = f"{b.court_id}:{(b.booking_date + timedelta(days=1)).isoformat()}"
            if mirror_key not in booked_slots:
                booked_slots[mirror_key] = []
            m2 = start_m
            while m2 < min(end_m, 8 * 60):
                ts2 = f"{m2//60:02d}:{m2%60:02d}"
                if ts2 not in booked_slots[mirror_key]:
                    booked_slots[mirror_key].append(ts2)
                m2 += 30

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

        name  = request.form['customer_name']
        phone = request.form['customer_phone']
        notes = request.form.get('notes', '')
        # end=00:00 means "ends exactly at midnight" — no next-day portion needed
        crosses_midnight = e_time < s_time and e_time != dtime(0, 0)

        if crosses_midnight:
            # Split into two bookings: tonight → 23:59, tomorrow 00:00 → end
            tomorrow = b_date + timedelta(days=1)
            midnight = dtime(23, 59)
            c1 = Booking.query.filter(Booking.court_id == court.id, Booking.booking_date == b_date,    Booking.status != 'cancelled', Booking.start_time < midnight,    Booking.end_time > s_time).first()
            c2 = Booking.query.filter(Booking.court_id == court.id, Booking.booking_date == tomorrow,  Booking.status != 'cancelled', Booking.start_time < e_time,       Booking.end_time > dtime(0, 0)).first()
            if c1 or c2:
                flash('عذراً، هذا الوقت محجوز بالفعل. يرجى اختيار وقت آخر.', 'danger')
                return redirect(url_for('booking.index'))
            bk1 = Booking(court_id=court.id, customer_name=name, customer_phone=phone, booking_date=b_date,   start_time=s_time,      end_time=midnight,  status='pending', notes=notes)
            bk2 = Booking(court_id=court.id, customer_name=name, customer_phone=phone, booking_date=tomorrow, start_time=dtime(0, 0), end_time=e_time,    status='pending', notes=notes, is_continuation=True)
            bk1.total_price = bk1.calc_price(court.price_per_hour)
            bk2.total_price = bk2.calc_price(court.price_per_hour)
            db.session.add_all([bk1, bk2])
            db.session.commit()
            try:
                from app.routes.admin import _send_push_all
                _send_push_all('حجز جديد', f'{name} — {court.name}', '/admin/bookings')
            except Exception:
                pass
            flash('تم استلام طلب حجزك بنجاح! سيتم التأكيد قريباً.', 'success')
            return redirect(url_for('booking.success', booking_id=bk1.id))

        # Normal (same-day) booking — overlap detection
        conflict = Booking.query.filter(
            Booking.court_id     == court.id,
            Booking.booking_date == b_date,
            Booking.status       != 'cancelled',
            Booking.start_time   < e_time,
            Booking.end_time     > s_time,
        ).first()
        if conflict:
            flash('عذراً، هذا الوقت محجوز بالفعل. يرجى اختيار وقت آخر.', 'danger')
            return redirect(url_for('booking.index'))

        bk = Booking(court_id=court.id, customer_name=name, customer_phone=phone,
                     booking_date=b_date, start_time=s_time, end_time=e_time,
                     status='pending', notes=notes)
        bk.total_price = bk.calc_price(court.price_per_hour)
        db.session.add(bk)
        db.session.commit()
        try:
            from app.routes.admin import _send_push_all
            _send_push_all('حجز جديد', f'{name} — {court.name}', '/admin/bookings')
        except Exception:
            pass
        flash('تم استلام طلب حجزك بنجاح! سيتم التأكيد قريباً.', 'success')
        return redirect(url_for('booking.success', booking_id=bk.id))
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ: {e}', 'danger')
        return redirect(url_for('booking.index'))



@booking_bp.route('/success/<int:booking_id>')
def success(booking_id):
    bk = Booking.query.get_or_404(booking_id)
    # Detect cross-midnight split: part 1 ends at 23:59, look for continuation tomorrow
    linked = None
    if bk.end_time and bk.end_time.hour == 23 and bk.end_time.minute == 59:
        tomorrow = bk.booking_date + timedelta(days=1)
        linked = Booking.query.filter_by(
            court_id=bk.court_id,
            booking_date=tomorrow,
            start_time=dtime(0, 0),
            customer_phone=bk.customer_phone,
        ).filter(Booking.status != 'cancelled').first()
    return render_template('booking_success.html', booking=bk, linked=linked)