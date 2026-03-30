from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models import Court, Booking
from app import db
from datetime import datetime

booking = Blueprint('booking', __name__)

@booking.route('/booking', methods=['GET', 'POST'])
def book():
    courts = Court.query.filter_by(is_active=True).all()
    selected_court = request.args.get('court')
    if request.method == 'POST':
        court_id = request.form.get('court_id')
        court = Court.query.get(court_id)
        date_str = request.form.get('date')
        start_str = request.form.get('start_time')
        end_str = request.form.get('end_time')
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        start_time = datetime.strptime(start_str, '%H:%M').time()
        end_time = datetime.strptime(end_str, '%H:%M').time()
        conflict = Booking.query.filter_by(
            court_id=court_id, date=date, status='confirmed'
        ).filter(
            Booking.start_time < end_time,
            Booking.end_time > start_time
        ).first()
        if conflict:
            flash('sorry, this time is already booked. please choose another time.')
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