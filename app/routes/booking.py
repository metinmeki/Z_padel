from flask import Blueprint, render_template, redirect, url_for, request, flash
from datetime import datetime, date, time as dtime, timedelta
from app import db
from app.models.main import Court, Booking, PricingRule

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
            'id':               c.id,
            'name':             c.name,
            'price_per_hour':   c.price_per_hour or 25000,
            'color':            c.color or '#1565C0',
            'use_time_pricing': bool(c.use_time_pricing is not False and c.use_time_pricing != 0),
        })

    # Build booked slots dict: {"court_id:date": ["HH:MM", ...]} covering every 30-min interval
    booked_slots = {}
    bookings = Booking.query.filter(Booking.status != 'cancelled').all()

    # Pre-collect (court_id, date) pairs that have a bk2 continuation — including
    # cancelled ones. This prevents bk1 from overflowing to the next day even when
    # its paired bk2 was cancelled or has a wrong end_time due to admin editing.
    continuation_keys = {
        (b.court_id, b.booking_date)
        for b in Booking.query.filter_by(is_continuation=True).all()
    }
    # Also treat non-continuation bookings in 00:00–02:59 as "next-day" slots that
    # belong to the previous business day.  This prevents bk1 from spilling into a
    # date that already has such a booking.
    continuation_keys |= {
        (b.court_id, b.booking_date)
        for b in bookings
        if not b.is_continuation and b.start_time and b.start_time.hour < 3
    }

    for b in bookings:
        if not b.start_time or not b.end_time:
            continue
        # Display rule: both is_continuation bk2 records AND non-continuation bookings
        # that start between 00:00–02:59 (bottom-row slots) belong to the PREVIOUS
        # business day's grid.
        is_bottom_row = (not b.is_continuation and b.start_time.hour < 3)
        display_date = (b.booking_date - timedelta(days=1)) if (b.is_continuation or is_bottom_row) else b.booking_date
        key = f"{b.court_id}:{display_date.isoformat()}"
        if key not in booked_slots:
            booked_slots[key] = []
        start_m = b.start_time.hour * 60 + b.start_time.minute
        end_m   = b.end_time.hour   * 60 + b.end_time.minute
        if end_m < start_m:  # cross-midnight: extend end past 24h boundary
            end_m += 24 * 60
        next_key = None
        m = start_m
        while m < end_m:
            if m >= 24 * 60 and not b.is_continuation:
                # Single cross-midnight record (not split into bk1+bk2).
                # If a paired bk2 continuation exists, it handles the overflow
                # display itself — skip. Otherwise add the overflow slot to the
                # SAME date key so the bottom row of THIS date's grid shows it
                # as booked (the frontend checks "court:date" for bottom-row slots).
                next_day = b.booking_date + timedelta(days=1)
                if (b.court_id, next_day) not in continuation_keys:
                    actual_m = m - 24 * 60
                    ts = f"{actual_m//60:02d}:{actual_m%60:02d}"
                    if ts not in booked_slots[key]:
                        booked_slots[key].append(ts)
            else:
                ts = f"{m//60:02d}:{m%60:02d}"
                if ts not in booked_slots[key]:
                    booked_slots[key].append(ts)
            m += 30


    pricing_rules = [
        {'start': r.start_hour, 'end': r.end_hour, 'price': r.price_per_hour}
        for r in PricingRule.query.filter_by(is_active=True).order_by(PricingRule.sort_order).all()
    ]

    return render_template('booking.html',
        courts=courts,
        courts_data=courts_data,
        today=today,
        booked_slots=booked_slots,
        pricing_rules=pricing_rules,
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
            _utp = court.use_time_pricing is not False and court.use_time_pricing != 0
            rate = (PricingRule.rate_for_hour(s_time.hour) if _utp else None) or court.price_per_hour
            bk1.total_price = bk1.calc_price(rate)
            bk2.total_price = bk2.calc_price(rate)
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
        rate = PricingRule.rate_for_hour(s_time.hour) or court.price_per_hour
        bk.total_price = bk.calc_price(rate)
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