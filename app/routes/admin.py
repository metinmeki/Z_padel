from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.models import Court, Booking
from app import db
import os
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

admin = Blueprint('admin', __name__)

@admin.route('/')
@login_required
def dashboard():
    total_courts = Court.query.count()
    total_bookings = Booking.query.count()
    confirmed_bookings = Booking.query.filter_by(status='confirmed').count()
    pending_bookings = Booking.query.filter_by(status='pending').count()
    recent_bookings = Booking.query.order_by(Booking.created_at.desc()).limit(10).all()
    return render_template('admin/dashboard.html',
        total_courts=total_courts,
        total_bookings=total_bookings,
        confirmed_bookings=confirmed_bookings,
        pending_bookings=pending_bookings,
        recent_bookings=recent_bookings
    )

@admin.route('/courts')
@login_required
def courts():
    all_courts = Court.query.all()
    return render_template('admin/courts.html', courts=all_courts)

@admin.route('/courts/add', methods=['GET', 'POST'])
@login_required
def add_court():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = request.form.get('price_per_hour')
        image_filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                image_filename = secure_filename(file.filename)
                file.save(os.path.join('app/static/images', image_filename))
        court = Court(
            name=name,
            description=description,
            price_per_hour=float(price),
            image=image_filename
        )
        db.session.add(court)
        db.session.commit()
        flash('تم إضافة الملعب بنجاح')
        return redirect(url_for('admin.courts'))
    return render_template('admin/add_court.html')

@admin.route('/courts/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_court(id):
    court = Court.query.get_or_404(id)
    if request.method == 'POST':
        court.name = request.form.get('name')
        court.description = request.form.get('description')
        court.price_per_hour = float(request.form.get('price_per_hour'))
        court.is_active = 'is_active' in request.form
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                image_filename = secure_filename(file.filename)
                file.save(os.path.join('app/static/images', image_filename))
                court.image = image_filename
        db.session.commit()
        flash('تم تحديث الملعب بنجاح')
        return redirect(url_for('admin.courts'))
    return render_template('admin/edit_court.html', court=court)

@admin.route('/courts/delete/<int:id>')
@login_required
def delete_court(id):
    court = Court.query.get_or_404(id)
    db.session.delete(court)
    db.session.commit()
    flash('تم حذف الملعب')
    return redirect(url_for('admin.courts'))


@admin.route('/bookings')
@login_required
def bookings():
    all_bookings = Booking.query.order_by(Booking.created_at.desc()).all()
    return render_template('admin/bookings.html', bookings=all_bookings)

@admin.route('/bookings/add', methods=['GET', 'POST'])
@login_required
def add_booking():
    courts = Court.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        court_id = request.form.get('court_id')
        court = Court.query.get(court_id)
        from datetime import datetime, time
        date_str = request.form.get('date')
        start_str = request.form.get('start_time')
        end_str = request.form.get('end_time')
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        start_time = datetime.strptime(start_str, '%H:%M').time()
        end_time = datetime.strptime(end_str, '%H:%M').time()
        hours = (datetime.combine(date, end_time) - datetime.combine(date, start_time)).seconds / 3600
        total = hours * court.price_per_hour
        booking = Booking(
            customer_name=request.form.get('customer_name'),
            customer_phone=request.form.get('customer_phone'),
            court_id=court_id,
            date=date,
            start_time=start_time,
            end_time=end_time,
            total_price=total,
            status='confirmed',
            notes=request.form.get('notes')
        )
        db.session.add(booking)
        db.session.commit()
        flash('تم إضافة الحجز بنجاح')
        return redirect(url_for('admin.bookings'))
    return render_template('admin/add_booking.html', courts=courts)

@admin.route('/bookings/status/<int:id>/<status>')
@login_required
def update_booking_status(id, status):
    booking = Booking.query.get_or_404(id)
    booking.status = status
    db.session.commit()
    flash('تم تحديث حالة الحجز')
    return redirect(url_for('admin.bookings'))

@admin.route('/bookings/delete/<int:id>')
@login_required
def delete_booking(id):
    booking = Booking.query.get_or_404(id)
    db.session.delete(booking)
    db.session.commit()
    flash('تم حذف الحجز')
    return redirect(url_for('admin.bookings'))


