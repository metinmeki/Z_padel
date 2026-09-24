from flask import Blueprint, render_template, redirect, url_for, request, flash
from datetime import datetime, date, time as dtime, timedelta
from app import db
from app.models.main import Court, Booking, PricingRule

def _parse_time(t):
    """Parse HH:MM, treating 24:00 as 23:59."""
    if t == '24:00':
        return dtime(23, 59)
    return datetime.strptime(t, '%H:%M').time()


def _tiered_price(court, s_time, e_time, use_time_pricing=True):
    """Price a booking per 30-min slot so cross-boundary bookings charge correctly.

    Example: 17:30-19:00 with off-peak(8-18)=25k, peak(18-22)=40k
      → 17:30-18:00 = 0.5h × 25k = 12,500
      → 18:00-19:00 = 1.0h × 40k = 40,000
      → total = 52,500  (not 37,500 from flat start-hour rate)
    """
    start_m = s_time.hour * 60 + s_time.minute
    end_m   = e_time.hour * 60 + e_time.minute
    if e_time == dtime(23, 59):
        end_m = 24 * 60
    if end_m < start_m:
        end_m += 24 * 60
    total = 0.0
    m = start_m
    while m < end_m:
        slot_end   = min(m + 30, end_m)
        slot_hours = (slot_end - m) / 60
        h = (m // 60) % 24
        rate = (PricingRule.rate_for_hour(h) if use_time_pricing else None) \
               or court.price_per_hour
        total += slot_hours * rate
        m += 30
    return round(total)


def _price_breakdown(court, s_time, e_time, use_time_pricing=True):
    """Return list of (from_ts, to_ts, rate, hours, subtotal) segments for display."""
    start_m = s_time.hour * 60 + s_time.minute
    end_m   = e_time.hour * 60 + e_time.minute
    if e_time == dtime(23, 59):
        end_m = 24 * 60
    if end_m < start_m:
        end_m += 24 * 60

    segments = []
    m = start_m
    seg_start = m
    seg_rate  = None

    def _ts(mins):
        return f"{(mins % 1440) // 60:02d}:{(mins % 1440) % 60:02d}"

    while m <= end_m:
        at_end = (m == end_m)
        if not at_end:
            h    = (m // 60) % 24
            rate = (PricingRule.rate_for_hour(h) if use_time_pricing else None) \
                   or court.price_per_hour
        # flush segment when rate changes or we've reached the end
        if (not at_end and seg_rate is not None and rate != seg_rate) or at_end:
            hours      = (m - seg_start) / 60
            hours_str  = f"{hours:g}"          # "1" not "1.0", "1.5" stays "1.5"
            subtotal   = round(hours * seg_rate)
            segments.append((_ts(seg_start), _ts(m), seg_rate, hours_str, subtotal))
            seg_start = m
            seg_rate  = rate if not at_end else seg_rate
        elif not at_end:
            seg_rate = rate
        m += 30

    return segments

booking_bp = Blueprint('booking', __name__)


def _migrate_to_business_dates():
    """One-time + ongoing migration to store all bookings under their business date.

    Business day: 08:00 on date D  →  03:00 on date D+1 (calendar).

    Steps (idempotent except step 3, which is guarded by a SystemSetting flag):
      1. Merge bk1+bk2 cross-midnight pairs into one record on the business date.
      2. Cancel any remaining orphaned bk2 records.
      3. (One-time) Remap old bottom-row bookings from calendar date to business date.
    """
    from app.models.main import SystemSetting
    changed = False

    # ── Step 1: merge bk1 (end=23:59) + bk2 (is_continuation, start=00:00) ──
    bk1_list = Booking.query.filter(
        Booking.is_continuation == False,
        Booking.end_time        == dtime(23, 59),
    ).all()
    for bk1 in bk1_list:
        next_date = bk1.booking_date + timedelta(days=1)
        bk2 = Booking.query.filter(
            Booking.court_id        == bk1.court_id,
            Booking.booking_date    == next_date,
            Booking.is_continuation == True,
            Booking.start_time      == dtime(0, 0),
        ).first()
        if bk2:
            bk1.end_time    = bk2.end_time
            bk1.total_price = (bk1.total_price or 0) + (bk2.total_price or 0)
            db.session.delete(bk2)
            changed = True

    # ── Step 2: cancel orphaned bk2 records (no active parent) ──
    orphans = Booking.query.filter(
        Booking.is_continuation == True,
        Booking.status          != 'cancelled',
    ).all()
    for orp in orphans:
        orp.status = 'cancelled'
        changed = True

    # ── Step 3: remap old-format bottom-row bookings to business date (one-time) ──
    # v2: re-run to catch bookings created by old admin code after v1 ran
    if not SystemSetting.get('bookings_biz_date_v2'):
        for b in Booking.query.filter(Booking.is_continuation == False).all():
            if b.start_time and b.start_time.hour < 3:
                b.booking_date = b.booking_date - timedelta(days=1)
                changed = True
        SystemSetting.set('bookings_biz_date_v2', 'done')
        changed = True

    if changed:
        db.session.commit()


@booking_bp.route('/')
def index():
    # Migrate existing data to business-date format (idempotent)
    _migrate_to_business_dates()

    courts = Court.query.filter_by(is_active=True).all()
    today  = date.today().isoformat()

    courts_data = []
    for c in courts:
        courts_data.append({
            'id':               c.id,
            'name':             c.name,
            'price_per_hour':   c.price_per_hour or 25000,
            'color':            c.color or '#1565C0',
            'use_time_pricing': bool(c.use_time_pricing is not False and c.use_time_pricing != 0),
        })

    # Build booked-slots dict: {"court_id:business_date": ["HH:MM", ...]}
    # After migration every booking.booking_date IS the business date.
    # Cross-midnight bookings (end_time < start_time) add post-midnight slots
    # to the SAME business-date key using modulo arithmetic.
    booked_slots = {}
    for b in Booking.query.filter(
        Booking.status          != 'cancelled',
        Booking.is_continuation == False,
    ).all():
        if not b.start_time or not b.end_time:
            continue
        key = f"{b.court_id}:{b.booking_date.isoformat()}"
        if key not in booked_slots:
            booked_slots[key] = []
        start_m = b.start_time.hour * 60 + b.start_time.minute
        end_m   = b.end_time.hour   * 60 + b.end_time.minute
        if end_m <= start_m and b.end_time != dtime(0, 0):
            end_m += 24 * 60          # cross-midnight: extend past 24h boundary
        elif b.end_time == dtime(0, 0):
            end_m = 24 * 60           # ends exactly at midnight
        m = start_m
        while m < end_m:
            ts = f"{(m % 1440) // 60:02d}:{(m % 1440) % 60:02d}"
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


def _biz_min(t):
    """Business-day minutes for time t. 00:00–02:59 treated as 24:00–26:59."""
    m = t.hour * 60 + t.minute
    return m + 1440 if t.hour < 3 else m


def _times_overlap(s1, e1, s2, e2):
    """True if [s1,e1] and [s2,e2] overlap within the same business day."""
    ms1, ms2 = _biz_min(s1), _biz_min(s2)
    me1 = 1440 if e1 == dtime(0, 0) else _biz_min(e1)
    me2 = 1440 if e2 == dtime(0, 0) else _biz_min(e2)
    if me1 <= ms1: me1 += 1440
    if me2 <= ms2: me2 += 1440
    return ms1 < me2 and ms2 < me1


@booking_bp.route('/create', methods=['POST'])
def create():
    try:
        court  = Court.query.get_or_404(request.form['court_id'])
        b_date = datetime.strptime(request.form['booking_date'], '%Y-%m-%d').date()
        s_time = _parse_time(request.form['start_time'])
        e_time = _parse_time(request.form['end_time'])

        if b_date < date.today():
            flash('لا يمكن الحجز في تاريخ سابق.', 'danger')
            return redirect(url_for('booking.index'))

        name  = request.form['customer_name']
        phone = request.form['customer_phone']
        notes = request.form.get('notes', '')

        # Conflict check using business-day overlap (handles cross-midnight)
        existing = Booking.query.filter(
            Booking.court_id        == court.id,
            Booking.booking_date    == b_date,
            Booking.status          != 'cancelled',
            Booking.is_continuation == False,
        ).all()
        if any(_times_overlap(s_time, e_time, b.start_time, b.end_time) for b in existing):
            flash('عذراً، هذا الوقت محجوز بالفعل. يرجى اختيار وقت آخر.', 'danger')
            return redirect(url_for('booking.index'))

        bk = Booking(court_id=court.id, customer_name=name, customer_phone=phone,
                     booking_date=b_date, start_time=s_time, end_time=e_time,
                     status='pending', notes=notes)
        _utp = court.use_time_pricing is not False and court.use_time_pricing != 0
        bk.total_price = _tiered_price(court, s_time, e_time, _utp)
        db.session.add(bk)
        db.session.commit()
        try:
            from app.routes.admin import _send_push_all
            _send_push_all('حجز جديد', f'{name} — {court.name}', '/admin/bookings')
        except Exception:
            pass
        from flask import session as flask_session
        flask_session['last_booking_id'] = bk.id
        flash('تم استلام طلب حجزك بنجاح! سيتم التأكيد قريباً.', 'success')
        return redirect(url_for('booking.success', booking_id=bk.id))
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ أثناء معالجة الحجز.', 'danger')
        return redirect(url_for('booking.index'))


@booking_bp.route('/success/<int:booking_id>')
def success(booking_id):
    from flask import session as flask_session
    if flask_session.get('last_booking_id') != booking_id:
        return redirect(url_for('booking.index'))
    bk = Booking.query.get_or_404(booking_id)

    breakdown = []
    if bk.start_time and bk.end_time and bk.court:
        _utp = bk.court.use_time_pricing is not False and bk.court.use_time_pricing != 0
        correct_price = _tiered_price(bk.court, bk.start_time, bk.end_time, _utp)
        if bk.total_price != correct_price:
            bk.total_price = correct_price
            db.session.commit()
        breakdown = _price_breakdown(bk.court, bk.start_time, bk.end_time, _utp)

    return render_template('booking_success.html', booking=bk, linked=None,
                           breakdown=breakdown)