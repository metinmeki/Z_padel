from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.models import Court, Booking
from app import db
from datetime import datetime

booking = Blueprint('booking', __name__)


@booking.route('/booking', methods=['GET', 'POST'])
def book():
    courts = Court.query.filter_by(is_active=True).all()
    selected_court = None
    court_param = request.args.get('court')
    if court_param:
        selected_court = Court.query.get(court_param)

    if request.method == 'POST':
        court_id  = request.form.get('court_id')
        court     = Court.query.get(court_id)
        date_str  = request.form.get('date')
        start_str = request.form.get('start_time')
        end_str   = request.form.get('end_time')

        date       = datetime.strptime(date_str, '%Y-%m-%d').date()
        start_time = datetime.strptime(start_str, '%H:%M').time()
        end_time   = datetime.strptime(end_str, '%H:%M').time()

        conflict = Booking.query.filter_by(
            court_id=court_id, date=date, status='confirmed'
        ).filter(
            Booking.start_time < end_time,
            Booking.end_time > start_time
        ).first()

        if conflict:
            flash('Sorry, this time is already booked. Please choose another time.')
            return render_template('booking.html', courts=courts, selected_court=selected_court)

        hours = (datetime.combine(date, end_time) - datetime.combine(date, start_time)).seconds / 3600
        total = hours * court.price_per_hour

        new_booking = Booking(
            customer_name=request.form.get('customer_name'),
            customer_phone=request.form.get('customer_phone'),
            court_id=court_id,
            date=date,
            start_time=start_time,
            end_time=end_time,
            total_price=total,
            status='pending',
            notes=request.form.get('notes')
        )
        db.session.add(new_booking)
        db.session.commit()
        return redirect(url_for('booking.success', booking_id=new_booking.id))

    return render_template('booking.html', courts=courts, selected_court=selected_court)


@booking.route('/booking/success/<int:booking_id>')
def success(booking_id):
    b = Booking.query.get_or_404(booking_id)
    return render_template('booking_success.html', booking=b)


@booking.route('/booking/availability')
def availability():
    court_id = request.args.get('court_id', type=int)
    date_str = request.args.get('date', '')

    if not court_id or not date_str:
        return jsonify({'booked_hours': []})

    try:
        sel_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'booked_hours': []})

    bookings = Booking.query.filter(
        Booking.court_id == court_id,
        Booking.date == sel_date,
        Booking.status.in_(['confirmed', 'pending'])
    ).all()

    booked_hours = []
    for b in bookings:
        start = b.start_time.hour
        end   = b.end_time.hour if b.end_time.hour != 0 else 24
        for h in range(start, end):
            booked_hours.append(h % 24)

    return jsonify({'booked_hours': list(set(booked_hours))})