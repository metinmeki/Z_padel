from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app.models import Court, Booking
from app.models.store import Product, Order, OrderItem
from app import db
from datetime import date, datetime, time
import os
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

admin = Blueprint('admin', __name__)


# ─────────────────────────────────────────────
#  DASHBOARD
# ─────────────────────────────────────────────
@admin.route('/')
@login_required
def dashboard():
    total_courts       = Court.query.count()
    total_bookings     = Booking.query.count()
    confirmed_bookings = Booking.query.filter_by(status='confirmed').count()
    pending_bookings   = Booking.query.filter_by(status='pending').count()
    recent_bookings    = Booking.query.order_by(Booking.created_at.desc()).limit(10).all()
    return render_template('admin/dashboard.html',
        total_courts=total_courts,
        total_bookings=total_bookings,
        confirmed_bookings=confirmed_bookings,
        pending_bookings=pending_bookings,
        recent_bookings=recent_bookings
    )


# Pending requests

@admin.route('/requests')
@login_required
def pending_requests():
    requests = Booking.query.filter_by(status='pending') \
        .order_by(Booking.created_at.asc()).all()
    return render_template('admin/pending_requests.html', requests=requests)

# ─────────────────────────────────────────────
#  COURTS
# ─────────────────────────────────────────────
@admin.route('/courts')
@login_required
def courts():
    all_courts = Court.query.all()
    return render_template('admin/courts.html', courts=all_courts)


@admin.route('/courts/add', methods=['GET', 'POST'])
@login_required
def add_court():
    if request.method == 'POST':
        name           = request.form.get('name')
        description    = request.form.get('description')
        price          = request.form.get('price_per_hour')
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
        court.name           = request.form.get('name')
        court.description    = request.form.get('description')
        court.price_per_hour = float(request.form.get('price_per_hour'))
        court.is_active      = 'is_active' in request.form
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


# ─────────────────────────────────────────────
#  ALL BOOKINGS
# ─────────────────────────────────────────────
@admin.route('/bookings')
@login_required
def bookings():
    date_from_str   = request.args.get('date_from', '')
    date_to_str     = request.args.get('date_to', '')
    single_date_str = request.args.get('single_date', '')
    court_filter    = request.args.get('court_id', 'all')
    status_filter   = request.args.get('status', 'all')
    search          = request.args.get('search', '').strip()
    page            = request.args.get('page', 1, type=int)
    per_page        = 25

    query = Booking.query

    if single_date_str:
        try:
            sd = datetime.strptime(single_date_str, '%Y-%m-%d').date()
            query = query.filter(Booking.date == sd)
        except ValueError:
            pass
    else:
        if date_from_str:
            try:
                query = query.filter(Booking.date >= datetime.strptime(date_from_str, '%Y-%m-%d').date())
            except ValueError:
                pass
        if date_to_str:
            try:
                query = query.filter(Booking.date <= datetime.strptime(date_to_str, '%Y-%m-%d').date())
            except ValueError:
                pass

    if court_filter != 'all':
        query = query.filter(Booking.court_id == int(court_filter))
    if status_filter != 'all':
        query = query.filter(Booking.status == status_filter)
    if search:
        query = query.filter(
            db.or_(
                Booking.customer_name.ilike(f'%{search}%'),
                Booking.customer_phone.ilike(f'%{search}%'),
            )
        )

    query      = query.order_by(Booking.date.desc(), Booking.start_time.asc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    all_filtered = query.all()
    stats = {
        'total':     pagination.total,
        'confirmed': sum(1 for b in all_filtered if b.status == 'confirmed'),
        'pending':   sum(1 for b in all_filtered if b.status == 'pending'),
        'cancelled': sum(1 for b in all_filtered if b.status in ('cancelled', 'rejected')),
    }
    all_courts = Court.query.all()

    return render_template(
        'admin/bookings.html',
        bookings=pagination.items,
        pagination=pagination,
        courts=all_courts,
        stats=stats,
        date_from=date_from_str,
        date_to=date_to_str,
        single_date=single_date_str,
        court_filter=court_filter,
        status_filter=status_filter,
        search=search,
    )


@admin.route('/bookings/add', methods=['GET', 'POST'])
@login_required
def add_booking():
    courts = Court.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        court_id   = request.form.get('court_id')
        court      = Court.query.get(court_id)
        date_str   = request.form.get('date')
        start_str  = request.form.get('start_time')
        end_str    = request.form.get('end_time')
        bdate      = datetime.strptime(date_str, '%Y-%m-%d').date()
        start_time = datetime.strptime(start_str, '%H:%M').time()
        end_time   = datetime.strptime(end_str, '%H:%M').time()
        hours      = (datetime.combine(bdate, end_time) - datetime.combine(bdate, start_time)).seconds / 3600
        total      = hours * court.price_per_hour
        booking = Booking(
            customer_name=request.form.get('customer_name'),
            customer_phone=request.form.get('customer_phone'),
            court_id=court_id,
            date=bdate,
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


@admin.route('/bookings/<int:id>/approve', methods=['POST'])
@login_required
def approve_booking(id):
    booking = Booking.query.get_or_404(id)
    booking.status = 'confirmed'
    db.session.commit()
    return jsonify({'success': True})


@admin.route('/bookings/<int:id>/reject', methods=['POST'])
@login_required
def reject_booking(id):
    data = request.get_json(silent=True) or {}
    booking = Booking.query.get_or_404(id)
    booking.status = 'rejected'
    if hasattr(booking, 'rejection_reason'):
        booking.rejection_reason = data.get('reason', '')
    db.session.commit()
    return jsonify({'success': True})


@admin.route('/bookings/<int:id>/delete', methods=['POST'])
@login_required
def delete_booking_ajax(id):
    booking = Booking.query.get_or_404(id)
    db.session.delete(booking)
    db.session.commit()
    return jsonify({'success': True})


@admin.route('/bookings/delete/<int:id>')
@login_required
def delete_booking(id):
    booking = Booking.query.get_or_404(id)
    db.session.delete(booking)
    db.session.commit()
    flash('تم حذف الحجز')
    return redirect(url_for('admin.bookings'))


# ─────────────────────────────────────────────
#  ORDERS (store)
# ─────────────────────────────────────────────
@admin.route('/orders')
@login_required
def orders():
    status_filter = request.args.get('status', 'all')
    query = Order.query
    if status_filter != 'all':
        query = query.filter(Order.status == status_filter)
    all_orders = query.order_by(Order.created_at.desc()).all()
    stats = {
        'total':     Order.query.count(),
        'pending':   Order.query.filter_by(status='pending').count(),
        'ready':     Order.query.filter_by(status='ready').count(),
        'done':      Order.query.filter_by(status='done').count(),
        'cancelled': Order.query.filter_by(status='cancelled').count(),
    }
    return render_template('admin/orders.html', orders=all_orders, stats=stats, status_filter=status_filter)


@admin.route('/orders/<int:order_id>/status', methods=['POST'])
@login_required
def update_order_status(order_id):
    order  = Order.query.get_or_404(order_id)
    data   = request.get_json(silent=True) or {}
    status = data.get('status')
    if status in ('pending', 'ready', 'done', 'cancelled'):
        order.status = status
        db.session.commit()
        return jsonify({'success': True, 'status': status})
    return jsonify({'success': False, 'message': 'Invalid status'})


@admin.route('/orders/<int:order_id>/delete', methods=['POST'])
@login_required
def delete_order(order_id):
    order = Order.query.get_or_404(order_id)
    db.session.delete(order)
    db.session.commit()
    return jsonify({'success': True})


# ─────────────────────────────────────────────
#  PRODUCTS (store)
# ─────────────────────────────────────────────
PRODUCT_UPLOAD_FOLDER = 'app/static/images/products'

def save_product_image(file):
    if file and allowed_file(file.filename):
        os.makedirs(PRODUCT_UPLOAD_FOLDER, exist_ok=True)
        fname = secure_filename(file.filename)
        file.save(os.path.join(PRODUCT_UPLOAD_FOLDER, fname))
        return fname
    return None


@admin.route('/products')
@login_required
def products():
    all_products = Product.query.order_by(Product.id.desc()).all()
    return render_template('admin/products.html', products=all_products)


@admin.route('/products/add', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        image = save_product_image(request.files.get('image'))
        p = Product(
            name        = request.form.get('name'),
            description = request.form.get('description'),
            price       = float(request.form.get('price', 0)),
            stock       = int(request.form.get('stock', 0)),
            is_active   = 'is_active' in request.form,
            image       = image
        )
        db.session.add(p)
        db.session.commit()
        flash('تم إضافة المنتج')
        return redirect(url_for('admin.products'))
    return render_template('admin/product_form.html', product=None)


@admin.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    p = Product.query.get_or_404(product_id)
    if request.method == 'POST':
        p.name        = request.form.get('name')
        p.description = request.form.get('description')
        p.price       = float(request.form.get('price', 0))
        p.stock       = int(request.form.get('stock', 0))
        p.is_active   = 'is_active' in request.form
        new_image     = save_product_image(request.files.get('image'))
        if new_image:
            p.image = new_image
        db.session.commit()
        flash('تم تحديث المنتج')
        return redirect(url_for('admin.products'))
    return render_template('admin/product_form.html', product=p)


@admin.route('/products/delete/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    p = Product.query.get_or_404(product_id)
    db.session.delete(p)
    db.session.commit()
    return jsonify({'success': True})


@admin.route('/products/toggle/<int:product_id>', methods=['POST'])
@login_required
def toggle_product(product_id):
    p = Product.query.get_or_404(product_id)
    p.is_active = not p.is_active
    db.session.commit()
    return jsonify({'success': True, 'is_active': p.is_active})


@admin.route('/pos')
@login_required
def pos():
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    return render_template('admin/pos.html', products=products)


@admin.route('/pos/checkout', methods=['POST'])
@login_required
def pos_checkout():
    from app.models.store import Order, OrderItem
    data = request.get_json(silent=True) or {}

    items = data.get('items', [])
    total = data.get('total', 0)
    cust_name = data.get('customer_name', 'زبون POS')
    cust_phone = data.get('customer_phone', '—')
    pay_method = data.get('pay_method', 'cash')

    if not items:
        return jsonify({'success': False, 'message': 'لا توجد منتجات'})

    try:
        order = Order(
            customer_name=cust_name,
            customer_phone=cust_phone,
            total_price=total,
            status='done',  # POS orders are instant
            source='pos',
            notes=f'دفع: {pay_method}'
        )
        db.session.add(order)
        db.session.flush()

        for item in items:
            p = Product.query.get(item['product_id'])
            if not p:
                continue
            db.session.add(OrderItem(
                order_id=order.id,
                product_id=p.id,
                quantity=item['qty'],
                unit_price=item['unit_price']
            ))
            # Deduct stock
            if p.stock > 0:
                p.stock = max(0, p.stock - item['qty'])

        db.session.commit()
        return jsonify({'success': True, 'order_id': order.id})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})
