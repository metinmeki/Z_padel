import os, uuid
from datetime import datetime, date, timedelta
from flask import (Blueprint, render_template, redirect, url_for,
                   request, flash, current_app, send_file)
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import func
from app import db
from app.models.main  import (Admin, Court, Booking, CancelRequest,
                               Coach, TrainingRequest, SystemSetting)
from app.models.store import (Category, Product, Order, OrderItem,
                               Expense, ExpenseCategory)
from sqlalchemy import func, case
admin_bp = Blueprint('admin', __name__)

# ── helpers ──
def allowed_file(filename):
    return ('.' in filename and
            filename.rsplit('.', 1)[1].lower()
            in current_app.config['ALLOWED_EXTENSIONS'])

def save_upload(file, folder_key='UPLOAD_FOLDER'):
    if not file or file.filename == '':
        return None
    ext = file.filename.rsplit('.', 1)[1].lower()
    if ext not in ['jpg', 'jpeg', 'png', 'webp', 'gif']:
        return None
    name = f"{uuid.uuid4().hex}.{ext}"
    # Always save to static/images/uploads/ so url_for('static') works
    upload_dir = os.path.join(current_app.static_folder, 'images', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    file.save(os.path.join(upload_dir, name))
    return name

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_active:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


# ════════════════════════════════════════════
# DASHBOARD
# ════════════════════════════════════════════
@admin_bp.route('/')
@admin_bp.route('/dashboard')
@login_required
def dashboard():
    today = date.today()
    now_h = datetime.now().hour

    total_bookings   = Booking.query.count()
    today_bookings   = Booking.query.filter_by(booking_date=today).count()
    pending_count    = Booking.query.filter_by(status='pending').count()
    confirmed_count  = Booking.query.filter_by(status='confirmed').count()
    cancelled_count  = Booking.query.filter_by(status='cancelled').count()
    total_orders     = Order.query.count()

    today_revenue = (db.session.query(func.sum(Booking.total_price))
                     .filter(Booking.booking_date == today,
                             Booking.status == 'confirmed').scalar() or 0)

    month_start   = today.replace(day=1)
    month_revenue = (db.session.query(func.sum(Booking.total_price))
                     .filter(Booking.booking_date >= month_start,
                             Booking.status == 'confirmed').scalar() or 0)

    week_start    = today - timedelta(days=6)
    week_revenue  = (db.session.query(func.sum(Booking.total_price))
                     .filter(Booking.booking_date >= week_start,
                             Booking.status == 'confirmed').scalar() or 0)

    store_revenue = (db.session.query(func.sum(Order.total_price))
                     .filter_by(status='completed').scalar() or 0)

    courts          = Court.query.filter_by(is_active=True).all()
    recent_bookings = (Booking.query.order_by(Booking.created_at.desc())
                       .limit(8).all())

    # Chart data — last 7 days
    week_labels, week_data, week_revenue_data = [], [], []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        week_labels.append(d.strftime('%a'))
        cnt = Booking.query.filter_by(booking_date=d, status='confirmed').count()
        rev = (db.session.query(func.sum(Booking.total_price))
               .filter_by(booking_date=d, status='confirmed').scalar() or 0)
        week_data.append(cnt)
        week_revenue_data.append(int(rev))

    return render_template('admin/dashboard.html',
        total_bookings=total_bookings, today_bookings=today_bookings,
        pending_count=pending_count, confirmed_count=confirmed_count,
        cancelled_count=cancelled_count, total_orders=total_orders,
        today_revenue=today_revenue, month_revenue=month_revenue,
        week_revenue=week_revenue, store_revenue=store_revenue,
        courts=courts, recent_bookings=recent_bookings,
        current_hour=now_h,
        week_labels=week_labels, week_data=week_data,
        week_revenue_data=week_revenue_data,
    )


# ════════════════════════════════════════════
# BOOKINGS
# ════════════════════════════════════════════
@admin_bp.route('/bookings')
@login_required
def bookings():
    q = Booking.query
    if request.args.get('date'):
        q = q.filter_by(booking_date=datetime.strptime(request.args['date'], '%Y-%m-%d').date())
    if request.args.get('court_id'):
        q = q.filter_by(court_id=request.args['court_id'])
    if request.args.get('status'):
        q = q.filter_by(status=request.args['status'])

    page   = request.args.get('page', 1, type=int)
    pag    = q.order_by(Booking.booking_date.desc(), Booking.start_time.asc()).paginate(page=page, per_page=20)
    courts = Court.query.filter_by(is_active=True).all()
    today  = date.today().isoformat()
    return render_template('admin/bookings.html',
        bookings=pag.items, pagination=pag,
        courts=courts, today=today, court_price=25000)


@admin_bp.route('/bookings/add', methods=['POST'])
@login_required
def add_booking():
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
            status=request.form.get('status', 'confirmed'),
            notes=request.form.get('notes', ''),
        )
        bk.total_price = bk.calc_price(court.price_per_hour)
        db.session.add(bk)
        db.session.commit()
        flash('تم إضافة الحجز بنجاح.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ: {e}', 'danger')
    return redirect(url_for('admin.bookings'))


@admin_bp.route('/bookings/<int:booking_id>')
@login_required
def booking_detail(booking_id):
    b = Booking.query.get_or_404(booking_id)
    return render_template('admin/booking_detail.html', booking=b)


@admin_bp.route('/bookings/<int:booking_id>/edit', methods=['POST'])
@login_required
def edit_booking(booking_id):
    b = Booking.query.get_or_404(booking_id)
    try:
        b.customer_name  = request.form.get('customer_name', b.customer_name)
        b.customer_phone = request.form.get('customer_phone', b.customer_phone)
        b.status         = request.form.get('status', b.status)
        b.notes          = request.form.get('notes', b.notes)
        db.session.commit()
        flash('تم تحديث الحجز.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'خطأ: {e}', 'danger')
    return redirect(url_for('admin.bookings'))


@admin_bp.route('/bookings/<int:booking_id>/confirm', methods=['GET', 'POST'])
@login_required
def confirm_booking(booking_id):
    b = Booking.query.get_or_404(booking_id)
    b.status = 'confirmed'
    db.session.commit()
    flash('تم تأكيد الحجز.', 'success')
    return redirect(url_for('admin.pending_bookings'))


@admin_bp.route('/bookings/<int:booking_id>/reject', methods=['GET', 'POST'])
@login_required
def reject_booking(booking_id):
    b = Booking.query.get_or_404(booking_id)
    b.status = 'cancelled'
    db.session.commit()
    flash('تم رفض الحجز.', 'success')
    return redirect(url_for('admin.pending_bookings'))


@admin_bp.route('/bookings/<int:booking_id>/cancel', methods=['POST'])
@login_required
def cancel_booking(booking_id):
    b = Booking.query.get_or_404(booking_id)
    b.status = 'cancelled'
    db.session.commit()
    flash('تم إلغاء الحجز.', 'success')
    return redirect(url_for('admin.bookings'))


@admin_bp.route('/bookings/confirm-all-pending')
@login_required
def confirm_all_pending():
    Booking.query.filter_by(status='pending').update({'status': 'confirmed'})
    db.session.commit()
    flash('تم تأكيد جميع الحجوزات المعلقة.', 'success')
    return redirect(url_for('admin.pending_bookings'))


@admin_bp.route('/pending-bookings')
@login_required
def pending_bookings():
    pending = Booking.query.filter_by(status='pending').order_by(Booking.created_at.asc()).all()
    courts  = Court.query.filter_by(is_active=True).all()
    today   = date.today()
    now     = datetime.utcnow()

    urgent  = sum(1 for b in pending if (now - b.created_at).total_seconds() > 7200)
    today_p = sum(1 for b in pending if b.booking_date == today)

    # Fix: use datetime(today.year, today.month, today.day) instead of datetime.combine
    today_start = datetime(today.year, today.month, today.day, 0, 0, 0)
    conf_t = Booking.query.filter(
        Booking.status == 'confirmed',
        Booking.updated_at >= today_start
    ).count()

    return render_template('admin/pending_bookings.html',
        pending_bookings=pending, courts=courts,
        urgent_count=urgent, today_pending=today_p, confirmed_today=conf_t)

# ════════════════════════════════════════════
# CANCEL REQUESTS
# ════════════════════════════════════════════
@admin_bp.route('/cancel-requests')
@login_required
def cancel_requests():
    reqs = CancelRequest.query.order_by(CancelRequest.created_at.desc()).all()
    approved_count = CancelRequest.query.filter_by(status='approved').count()
    rejected_count = CancelRequest.query.filter_by(status='rejected').count()
    return render_template('admin/cancel_requests.html',
        cancel_requests=reqs,
        approved_count=approved_count,
        rejected_count=rejected_count)


@admin_bp.route('/cancel-requests/<int:req_id>/approve', methods=['POST'])
@login_required
def approve_cancel(req_id):
    cr = CancelRequest.query.get_or_404(req_id)
    cr.status = 'approved'
    cr.booking.status = 'cancelled'
    db.session.commit()
    flash('تم قبول طلب الإلغاء.', 'success')
    return redirect(url_for('admin.cancel_requests'))


@admin_bp.route('/cancel-requests/<int:req_id>/reject', methods=['POST'])
@login_required
def reject_cancel(req_id):
    cr = CancelRequest.query.get_or_404(req_id)
    cr.status = 'rejected'
    db.session.commit()
    flash('تم رفض طلب الإلغاء.', 'success')
    return redirect(url_for('admin.cancel_requests'))


# ════════════════════════════════════════════
# COURTS
# ════════════════════════════════════════════
@admin_bp.route('/courts')
@login_required
def courts():
    all_courts = Court.query.all()
    return render_template('admin/courts.html', courts=all_courts)


@admin_bp.route('/courts/add', methods=['POST'])
@login_required
def add_court():
    court = Court(
        name=request.form['name'],
        price_per_hour=float(request.form.get('price_per_hour', 25000)),
        color=request.form.get('color', '#1565C0'),
        description=request.form.get('description', ''),
        capacity=request.form.get('capacity') or None,
        surface_type=request.form.get('surface_type', ''),
    )
    db.session.add(court)
    db.session.commit()
    flash('تم إضافة الملعب بنجاح.', 'success')
    return redirect(url_for('admin.courts'))


@admin_bp.route('/courts/<int:court_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_court(court_id):
    court = Court.query.get_or_404(court_id)
    if request.method == 'POST':
        court.name           = request.form.get('name', court.name)
        court.price_per_hour = float(request.form.get('price_per_hour', court.price_per_hour or 25000))
        court.color          = request.form.get('color', court.color)
        court.description    = request.form.get('description', court.description)
        court.capacity       = request.form.get('capacity') or None
        court.surface_type   = request.form.get('surface_type', court.surface_type)
        court.is_active      = request.form.get('is_active', '1') == '1'
        if request.form.get('remove_image'):
            court.image = None
        new_img = save_upload(request.files.get('image'))
        if new_img:
            court.image = new_img
        db.session.commit()
        flash('تم تحديث الملعب بنجاح.', 'success')
        return redirect(url_for('admin.courts'))
    return render_template('admin/edit_court.html', court=court)


@admin_bp.route('/courts/<int:court_id>/toggle', methods=['POST'])
@login_required
def toggle_court(court_id):
    c = Court.query.get_or_404(court_id)
    c.is_active = not c.is_active
    db.session.commit()
    return redirect(url_for('admin.courts'))


@admin_bp.route('/courts/<int:court_id>/delete', methods=['POST'])
@login_required
def delete_court(court_id):
    c = Court.query.get_or_404(court_id)
    db.session.delete(c)
    db.session.commit()
    flash('تم حذف الملعب.', 'success')
    return redirect(url_for('admin.courts'))


# ════════════════════════════════════════════
# PRODUCTS
# ════════════════════════════════════════════
@admin_bp.route('/products')
@login_required
def products():
    prods = Product.query.order_by(Product.created_at.desc()).all()
    cats  = Category.query.all()
    return render_template('admin/products.html', products=prods, categories=cats)


@admin_bp.route('/products/new', methods=['GET', 'POST'])
@login_required
def new_product():
    cats = Category.query.all()
    if request.method == 'POST':
        img = save_upload(request.files.get('image'))
        p = Product(
            name=request.form['name'],
            category_id=request.form.get('category_id') or None,
            price=float(request.form.get('price', 0)),
            stock=int(request.form.get('stock', 0)),
            description=request.form.get('description', ''),
            barcode=request.form.get('barcode') or None,
            show_on_website=request.form.get('show_on_website') == '1',
            is_active='is_active' in request.form,
            image=img,
        )
        db.session.add(p)
        db.session.commit()
        flash('تم إضافة المنتج بنجاح.', 'success')
        return redirect(url_for('admin.products'))
    return render_template('admin/product_form.html', product=None, categories=cats)


@admin_bp.route('/products/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    p    = Product.query.get_or_404(product_id)
    cats = Category.query.all()
    if request.method == 'POST':
        p.name            = request.form.get('name', p.name)
        p.price           = float(request.form.get('price', p.price))
        p.stock           = int(request.form.get('stock', p.stock))
        p.description     = request.form.get('description', p.description)
        p.barcode         = request.form.get('barcode') or p.barcode
        p.category_id     = request.form.get('category_id') or p.category_id
        p.show_on_website = request.form.get('show_on_website') == '1'
        p.is_active       = 'is_active' in request.form
        new_img = save_upload(request.files.get('image'))
        if new_img:
            p.image = new_img
        db.session.commit()
        flash('تم تحديث المنتج.', 'success')
        return redirect(url_for('admin.products'))
    return render_template('admin/product_form.html', product=p, categories=cats)

@admin_bp.route('/products/<int:product_id>/delete', methods=['POST'])
@login_required
def delete_product(product_id):
    p = Product.query.get_or_404(product_id)
    db.session.delete(p)
    db.session.commit()
    flash('تم حذف المنتج.', 'success')
    return redirect(url_for('admin.products'))


# ════════════════════════════════════════════
# CATEGORIES
# ════════════════════════════════════════════
@admin_bp.route('/categories')
@login_required
def categories():
    cats = Category.query.all()
    return render_template('admin/categories.html', categories=cats)


@admin_bp.route('/categories/add', methods=['POST'])
@login_required
def add_category():
    cat = Category(name=request.form['name'],
                   color=request.form.get('color', '#1565C0'))
    db.session.add(cat)
    db.session.commit()
    flash('تم إضافة الفئة.', 'success')
    return redirect(url_for('admin.categories'))


@admin_bp.route('/categories/<int:cat_id>/delete', methods=['POST'])
@login_required
def delete_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    db.session.delete(cat)
    db.session.commit()
    flash('تم حذف الفئة.', 'success')
    return redirect(url_for('admin.categories'))


# ════════════════════════════════════════════
# ORDERS
# ════════════════════════════════════════════
from flask import jsonify, request

from flask import jsonify, request, render_template
from sqlalchemy.orm import joinedload  # Ensure this is imported


@admin_bp.route('/orders')
@login_required
def orders():
    # .options(joinedload(Order.items)) loads everything in 1 query, not 20+ queries
    q = Order.query.options(joinedload(Order.items))

    if request.args.get('status'):
        q = q.filter_by(status=request.args['status'])
    if request.args.get('date'):
        d = datetime.strptime(request.args['date'], '%Y-%m-%d').date()
        q = q.filter(func.date(Order.created_at) == d)

    page = request.args.get('page', 1, type=int)
    pag = q.order_by(Order.created_at.desc()).paginate(page=page, per_page=20)

    return render_template('admin/orders.html', orders=pag.items, pagination=pag)


@admin_bp.route('/orders/<int:order_id>/status', methods=['POST'])
@login_required
def update_order_status(order_id):
    o = Order.query.get_or_404(order_id)
    # Get status from the form
    o.status = request.form.get('status')
    db.session.commit()
    return jsonify({"success": True, "new_status": o.status})


@admin_bp.route('/orders/<int:order_id>/delete', methods=['POST'])
@login_required
def delete_order(order_id):
    o = Order.query.get_or_404(order_id)
    db.session.delete(o)
    db.session.commit()
    return jsonify({"success": True})
# ════════════════════════════════════════════
# EXPENSES
# ════════════════════════════════════════════
@admin_bp.route('/expenses')
@login_required
def expenses():
    from sqlalchemy import func
    from calendar import monthrange

    q = Expense.query
    if request.args.get('month'):
        y, m = map(int, request.args['month'].split('-'))
        last_day = monthrange(y, m)[1]
        q = q.filter(Expense.date >= date(y, m, 1),
                     Expense.date <= date(y, m, last_day))

    page = request.args.get('page', 1, type=int)
    pag = q.order_by(Expense.date.desc()).paginate(page=page, per_page=20)

    today = date.today()
    month_start = today.replace(day=1)

    cats = db.session.query(
        ExpenseCategory,
        func.sum(Expense.amount).label('total')
    ).outerjoin(Expense).group_by(ExpenseCategory.id).all()

    cats_with_totals = [
        {'id': c[0].id, 'name': c[0].name, 'color': c[0].color, 'total': c[1] or 0}
        for c in cats
    ]

    totals = db.session.query(
        func.sum(Expense.amount).label('total'),
        func.sum(case((Expense.date == today, Expense.amount), else_=0)).label('today'),
        func.sum(case((Expense.date >= month_start, Expense.amount), else_=0)).label('month')
    ).first()

    total_exp = totals.total or 0
    today_exp = totals.today or 0
    month_exp = totals.month or 0

    total_rev = (db.session.query(func.sum(Booking.total_price))
                 .filter_by(status='confirmed').scalar() or 0)

    monthly_trend = []
    for i in range(5, -1, -1):
        d = today.replace(day=1) - timedelta(days=i * 28)
        d = d.replace(day=1)
        nm = d.replace(day=28) + timedelta(days=4)
        nm = nm.replace(day=1)
        total = (db.session.query(func.sum(Expense.amount))
                 .filter(Expense.date >= d, Expense.date < nm).scalar() or 0)
        monthly_trend.append({'label': d.strftime('%b'), 'total': total})

    budget = float(SystemSetting.get('monthly_budget', 1_000_000))

    return render_template('admin/expenses.html',
                           expenses=pag.items, pagination=pag,
                           expense_categories=cats_with_totals,
                           total_expenses=total_exp, today_expenses=today_exp,
                           month_expenses=month_exp, total_revenue=total_rev,
                           monthly_trend=monthly_trend, monthly_budget=budget,
                           today=today.isoformat(),
                           )


@admin_bp.route('/expenses/add', methods=['POST'])
@login_required
def add_expense():
    try:
        # ✅ receipt is optional — only save if a file was actually uploaded
        receipt = None
        file = request.files.get('receipt')
        if file and file.filename:
            receipt = save_upload(file, 'RECEIPTS_FOLDER')

        e = Expense(
            description=request.form['description'],
            amount=float(request.form['amount']),
            date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
            category_id=request.form.get('category_id') or None,
            notes=request.form.get('notes', ''),
            receipt=receipt,
            added_by=current_user.username,
        )
        db.session.add(e)
        db.session.commit()
        flash('تم إضافة المصروف.', 'success')
    except Exception as ex:
        db.session.rollback()
        flash(f'خطأ أثناء الإضافة: {ex}', 'danger')

    return redirect(url_for('admin.expenses'))


@admin_bp.route('/expenses/<int:exp_id>/edit', methods=['POST'])
@login_required
def edit_expense(exp_id):
    try:
        e = Expense.query.get_or_404(exp_id)
        e.description = request.form.get('description', e.description)
        e.amount      = float(request.form.get('amount', e.amount))
        e.date        = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
        e.category_id = request.form.get('category_id') or e.category_id
        e.notes       = request.form.get('notes', e.notes)
        db.session.commit()
        flash('تم تحديث المصروف.', 'success')
    except Exception as ex:
        db.session.rollback()
        flash(f'خطأ أثناء التعديل: {ex}', 'danger')

    return redirect(url_for('admin.expenses'))


@admin_bp.route('/expenses/<int:exp_id>/delete', methods=['POST'])
@login_required
def delete_expense(exp_id):
    try:
        e = Expense.query.get_or_404(exp_id)
        db.session.delete(e)
        db.session.commit()
        flash('تم حذف المصروف.', 'success')
    except Exception as ex:
        db.session.rollback()
        flash(f'خطأ أثناء الحذف: {ex}', 'danger')

    return redirect(url_for('admin.expenses'))


@admin_bp.route('/expenses/export')
@login_required
def export_expenses():
    flash('ميزة التصدير قيد التطوير.', 'info')
    return redirect(url_for('admin.expenses'))
# ════════════════════════════════════════════
# REPORTS
# ════════════════════════════════════════════
@admin_bp.route('/reports')
@login_required
def reports():
    today  = date.today()
    period = request.args.get('period', 'month')

    if period == 'today':
        start = today
    elif period == 'week':
        start = today - timedelta(days=6)
    elif period == 'year':
        start = today.replace(month=1, day=1)
    else:
        start = today.replace(day=1)

    bks = Booking.query.filter(Booking.booking_date >= start).all()
    total_rev  = sum(b.total_price or 0 for b in bks if b.status == 'confirmed')
    total_bks  = len(bks)
    conf_bks   = sum(1 for b in bks if b.status == 'confirmed')
    pend_bks   = sum(1 for b in bks if b.status == 'pending')
    canc_bks   = sum(1 for b in bks if b.status == 'cancelled')
    avg_val    = round(total_rev / conf_bks) if conf_bks else 0
    disc_bks   = sum(1 for b in bks if b.is_discount_slot and b.status == 'confirmed')
    disc_rev   = sum(b.total_price or 0 for b in bks if b.is_discount_slot and b.status == 'confirmed')
    disc_rate  = round(disc_bks / conf_bks * 100) if conf_bks else 0

    courts     = Court.query.all()
    court_names   = [c.name for c in courts]
    court_counts  = [Booking.query.filter_by(court_id=c.id, status='confirmed').count() for c in courts]
    court_colors  = [c.color for c in courts]

    top_courts = sorted(
        [{'name': c.name, 'revenue': sum(
            b.total_price or 0 for b in c.bookings if b.status == 'confirmed'
          )} for c in courts],
        key=lambda x: x['revenue'], reverse=True
    )[:5]

    top_products = (db.session.query(Product.name,
                    func.sum(OrderItem.quantity).label('sold'))
                    .join(OrderItem).group_by(Product.id)
                    .order_by(func.sum(OrderItem.quantity).desc())
                    .limit(5).all())

    # Chart labels/data
    labels, bk_data, rev_data = [], [], []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        labels.append(d.strftime('%a'))
        bk_data.append(Booking.query.filter_by(booking_date=d, status='confirmed').count())
        rev_data.append(int(db.session.query(func.sum(Booking.total_price))
                            .filter_by(booking_date=d, status='confirmed').scalar() or 0))

    hourly = [Booking.query.filter(
        Booking.start_time >= datetime.strptime(f'{h:02d}:00', '%H:%M').time(),
        Booking.start_time <  datetime.strptime(f'{(h+1)%24:02d}:00', '%H:%M').time(),
        Booking.status == 'confirmed').count()
        for h in range(24)]

    total_exp  = db.session.query(func.sum(Expense.amount)).scalar() or 0
    total_ords = Order.query.count()
    store_rev  = (db.session.query(func.sum(Order.total_price))
                  .filter_by(status='completed').scalar() or 0)
    total_slots = len(courts) * 18
    booked_today = sum(len(c.today_booked_slots) for c in courts)
    occ_rate = round(booked_today / total_slots * 100) if total_slots else 0

    return render_template('admin/reports.html',
        total_revenue=total_rev, total_bookings=total_bks,
        confirmed_bookings=conf_bks, pending_bookings_count=pend_bks,
        cancelled_bookings=canc_bks, avg_booking_value=avg_val,
        total_orders=total_ords, store_revenue=store_rev,
        total_expenses=total_exp, occupancy_rate=occ_rate,
        discount_bookings=disc_bks, discount_revenue=disc_rev,
        discount_rate=disc_rate,
        chart_labels=labels, bookings_data=bk_data, revenue_data=rev_data,
        hourly_data=hourly,
        court_names=court_names, court_counts=court_counts, court_colors=court_colors,
        top_courts=top_courts,
        top_products=[{'name': p.name, 'sold': p.sold} for p in top_products],
        current_period=period, courts=courts,
    )


@admin_bp.route('/reports/export')
@login_required
def export_report():
    flash('ميزة التصدير قيد التطوير.', 'info')
    return redirect(url_for('admin.reports'))


# ════════════════════════════════════════════
# USERS
# ════════════════════════════════════════════
# ════════════════════════════════════════════
# USERS
# ════════════════════════════════════════════

@admin_bp.route('/users')
@login_required
def users():
    all_users = Admin.query.all()
    return render_template('admin/users.html', users=all_users)


@admin_bp.route('/users/add', methods=['POST'])
@login_required
def add_user():
    if not current_user.has_perm('perm_users'):
        flash('ليس لديك صلاحية لإضافة مستخدمين.', 'danger')
        return redirect(url_for('admin.users'))

    if Admin.query.filter_by(username=request.form['username']).first():
        flash('اسم المستخدم مستخدم بالفعل.', 'danger')
        return redirect(url_for('admin.users'))

    u = Admin(
        username=request.form['username'],
        email=request.form.get('email') or None,
        password=generate_password_hash(request.form['password']),
        role=request.form.get('role', 'staff'),
        is_active=bool(int(request.form.get('is_active', 1))),
        permissions={},
    )
    db.session.add(u)
    db.session.commit()
    flash('تم إضافة المستخدم.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/edit', methods=['POST'])
@login_required
def edit_user(user_id):
    if not current_user.has_perm('perm_users'):
        flash('ليس لديك صلاحية لتعديل المستخدمين.', 'danger')
        return redirect(url_for('admin.users'))

    u = Admin.query.get_or_404(user_id)
    u.username  = request.form.get('username', u.username)
    u.email     = request.form.get('email', u.email) or u.email
    u.role      = request.form.get('role', u.role)
    u.is_active = bool(int(request.form.get('is_active', 1)))
    new_pwd = request.form.get('new_password', '').strip()
    if new_pwd:
        u.password = generate_password_hash(new_pwd)
    db.session.commit()
    flash('تم تحديث المستخدم.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/permissions', methods=['POST'])
@login_required
def edit_permissions(user_id):
    if not current_user.has_perm('perm_users'):
        flash('ليس لديك صلاحية لتعديل الصلاحيات.', 'danger')
        return redirect(url_for('admin.dashboard'))

    # Only superadmin can assign perm_users and perm_settings to others
    perm_keys = ['perm_bookings', 'perm_courts', 'perm_products', 'perm_orders',
                 'perm_expenses', 'perm_reports', 'perm_users', 'perm_settings']

    if current_user.role != 'superadmin':
        # non-superadmin cannot grant perm_users or perm_settings
        perm_keys = [k for k in perm_keys if k not in ('perm_users', 'perm_settings')]

    u = Admin.query.get_or_404(user_id)

    # Prevent editing a superadmin's permissions unless you are also superadmin
    if u.role == 'superadmin' and current_user.role != 'superadmin':
        flash('لا يمكنك تعديل صلاحيات المدير العام.', 'danger')
        return redirect(url_for('admin.users'))

    u.permissions = {k: (k in request.form) for k in perm_keys}
    db.session.commit()
    flash('تم تحديث الصلاحيات.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.has_perm('perm_users'):
        flash('ليس لديك صلاحية لحذف المستخدمين.', 'danger')
        return redirect(url_for('admin.users'))

    if user_id == current_user.id:
        flash('لا يمكنك حذف حسابك الخاص.', 'danger')
        return redirect(url_for('admin.users'))

    u = Admin.query.get_or_404(user_id)

    # Prevent deleting a superadmin unless you are also superadmin
    if u.role == 'superadmin' and current_user.role != 'superadmin':
        flash('لا يمكنك حذف حساب المدير العام.', 'danger')
        return redirect(url_for('admin.users'))

    db.session.delete(u)
    db.session.commit()
    flash('تم حذف المستخدم.', 'success')
    return redirect(url_for('admin.users'))


# ════════════════════════════════════════════
# SETTINGS
# ════════════════════════════════════════════
@admin_bp.route('/settings')
@login_required
def settings():
    keys = ['facility_name','phone','email','address','currency',
            'open_time','close_time','allow_midnight_bookings','late_close_time',
            'default_duration','max_advance_days','require_prepayment',
            'auto_confirm','allow_self_cancel','cancel_window_hours',
            'default_price','enable_discount','discount_percent',
            'discount_start','discount_end','monthly_budget',
            'store_enabled','min_order_amount','low_stock_alert','pos_enabled',
            'notif_new_booking','notif_cancel_request','notif_new_order',
            'notif_low_stock','notif_pending_review',
            'brand_color','admin_panel_name','enable_animations',
            'show_clock','session_timeout','log_failed_logins']
    cfg = {k: SystemSetting.get(k) for k in keys}
    return render_template('admin/settings.html', settings=cfg)


@admin_bp.route('/settings/save/<section>', methods=['POST'])
@login_required
def save_settings(section):
    for key, val in request.form.items():
        if key == 'csrf_token':
            continue
        SystemSetting.set(key, val)
    # Handle checkboxes (unchecked = not in form)
    checkbox_keys = {
        'general':       ['allow_midnight_bookings'],
        'booking':       ['require_prepayment','auto_confirm','allow_self_cancel'],
        'pricing':       ['enable_discount'],
        'store':         ['store_enabled','pos_enabled'],
        'notifications': ['notif_new_booking','notif_cancel_request',
                          'notif_new_order','notif_low_stock','notif_pending_review'],
        'appearance':    ['enable_animations','show_clock'],
        'security':      ['log_failed_logins'],
    }
    for key in checkbox_keys.get(section, []):
        SystemSetting.set(key, 'true' if key in request.form else 'false')
    flash('تم حفظ الإعدادات.', 'success')
    return redirect(url_for('admin.settings'))


# ════════════════════════════════════════════
# DANGER ZONE
# ════════════════════════════════════════════
@admin_bp.route('/danger/delete-cancelled', methods=['POST'])
@login_required
def danger_delete_cancelled():
    Booking.query.filter_by(status='cancelled').delete()
    db.session.commit()
    flash('تم حذف جميع الحجوزات الملغية.', 'success')
    return redirect(url_for('admin.settings'))


@admin_bp.route('/danger/reset-settings', methods=['POST'])
@login_required
def danger_reset_settings():
    SystemSetting.query.delete()
    db.session.commit()
    flash('تم إعادة تعيين الإعدادات.', 'success')
    return redirect(url_for('admin.settings'))


@admin_bp.route('/danger/export-backup')
@login_required
def export_backup():
    flash('ميزة النسخ الاحتياطي قيد التطوير.', 'info')
    return redirect(url_for('admin.settings'))


# ════════════════════════════════════════════
# NOTIFICATIONS API
# ════════════════════════════════════════════
@admin_bp.route('/api/notifications')
@login_required
def api_notifications():
    from flask import jsonify
    from app.models.main import CancelRequest, TrainingRequest
    from app.models.store import Product, Order

    pending_bookings  = Booking.query.filter_by(status='pending').count()
    cancel_requests   = CancelRequest.query.filter_by(status='pending').count()
    training_requests = TrainingRequest.query.filter_by(status='pending').count()
    low_stock         = Product.query.filter(Product.stock <= 5, Product.is_active == True).count()
    pending_orders    = Order.query.filter_by(status='pending').count()

    items = []
    if pending_bookings:
        items.append({
            'icon': 'fa-calendar-clock', 'color': '#FB8C00',
            'en': f'{pending_bookings} pending booking(s) awaiting review',
            'ar': f'يوجد {pending_bookings} حجز بانتظار المراجعة',
            'url': '/admin/pending-bookings'
        })
    if cancel_requests:
        items.append({
            'icon': 'fa-calendar-xmark', 'color': '#E53935',
            'en': f'{cancel_requests} cancellation request(s)',
            'ar': f'يوجد {cancel_requests} طلب إلغاء',
            'url': '/admin/cancel-requests'
        })
    if training_requests:
        items.append({
            'icon': 'fa-dumbbell', 'color': '#7B1FA2',
            'en': f'{training_requests} training request(s)',
            'ar': f'يوجد {training_requests} طلب تدريب',
            'url': '/admin/training-requests'
        })
    if low_stock:
        items.append({
            'icon': 'fa-box-open', 'color': '#F57C00',
            'en': f'{low_stock} product(s) low on stock',
            'ar': f'يوجد {low_stock} منتج ينفد مخزونه',
            'url': '/admin/products'
        })
    if pending_orders:
        items.append({
            'icon': 'fa-bag-shopping', 'color': '#1565C0',
            'en': f'{pending_orders} pending order(s)',
            'ar': f'يوجد {pending_orders} طلب معلق',
            'url': '/admin/orders'
        })

    return jsonify({
        'total': len(items),
        'items': items
    })


# ════════════════════════════════════════════
# MISC
# ════════════════════════════════════════════
@admin_bp.route('/print-barcodes')
@login_required
def print_barcodes():
    products = Product.query.filter(Product.barcode.isnot(None)).all()
    return render_template('admin/print_barcodes.html', products=products)



@admin_bp.route('/coaches')
@login_required
def coaches():
    from app.models.main import Coach
    all_coaches = Coach.query.all()
    return render_template('admin/coaches.html', coaches=all_coaches)


@admin_bp.route('/training-requests')
@login_required
def training_requests():
    from app.models.main import TrainingRequest, Coach
    reqs   = TrainingRequest.query.order_by(TrainingRequest.created_at.desc()).all()
    coaches = Coach.query.filter_by(is_active=True).all()
    return render_template('admin/training_requests.html',
        training_requests=reqs, coaches=coaches)


@admin_bp.route('/coaches/add', methods=['POST'])
@login_required
def add_coach():
    from app.models.main import Coach
    import os
    from werkzeug.utils import secure_filename

    # Handle image upload
    image_path = None
    if 'image' in request.files and request.files['image'].filename != '':
        file = request.files['image']
        if file:
            filename = secure_filename(file.filename)
            # Save to static/uploads/coaches/
            upload_dir = os.path.join('app/static/uploads/coaches')
            os.makedirs(upload_dir, exist_ok=True)
            file.save(os.path.join(upload_dir, filename))
            image_path = f'uploads/coaches/{filename}'  # ✅ Store relative path

    c = Coach(
        name=request.form['name'],
        phone=request.form.get('phone', ''),
        specialty=request.form.get('specialty', ''),
        price_per_hour=float(request.form.get('price_per_hour', 0)),
        bio=request.form.get('bio', ''),
        image=image_path,  # ✅ ADD THIS
        is_active=bool(int(request.form.get('is_active', 1))),
    )
    db.session.add(c)
    db.session.commit()
    flash('تم إضافة المدرب.', 'success')
    return redirect(url_for('admin.coaches'))


@admin_bp.route('/coaches/<int:coach_id>/edit', methods=['POST'])
@login_required
def edit_coach(coach_id):
    from app.models.main import Coach
    import os
    from werkzeug.utils import secure_filename

    c = Coach.query.get_or_404(coach_id)

    # Handle new image if uploaded
    if 'image' in request.files and request.files['image'].filename != '':
        file = request.files['image']
        filename = secure_filename(file.filename)
        upload_dir = os.path.join('app/static/uploads/coaches')
        os.makedirs(upload_dir, exist_ok=True)
        file.save(os.path.join(upload_dir, filename))
        c.image = f'uploads/coaches/{filename}'

    c.name = request.form.get('name', c.name)
    c.phone = request.form.get('phone', c.phone)
    c.specialty = request.form.get('specialty', c.specialty)
    c.price_per_hour = float(request.form.get('price_per_hour', c.price_per_hour))
    c.bio = request.form.get('bio', c.bio)
    c.is_active = bool(int(request.form.get('is_active', 1)))
    db.session.commit()
    flash('تم تحديث المدرب.', 'success')
    return redirect(url_for('admin.coaches'))
@admin_bp.route('/coaches/<int:coach_id>/delete', methods=['POST'])
@login_required
def delete_coach(coach_id):
    from app.models.main import Coach
    c = Coach.query.get_or_404(coach_id)
    db.session.delete(c)
    db.session.commit()
    flash('تم حذف المدرب.', 'success')
    return redirect(url_for('admin.coaches'))


@admin_bp.route('/training-requests/add', methods=['POST'])
def add_training_request():  # ✅ REMOVED @login_required (public form)
    from app.models.main import TrainingRequest
    from datetime import datetime

    # ✅ Validate coach_id is provided
    coach_id = request.form.get('coach_id')
    if not coach_id:
        flash('يرجى اختيار مدرب.', 'error')
        return redirect(request.referrer or url_for('main.index'))

    try:
        tr = TrainingRequest(
            customer_name=request.form['customer_name'],
            customer_phone=request.form['customer_phone'],
            coach_id=int(coach_id),  # ✅ Convert to int
            preferred_date=datetime.strptime(request.form['preferred_date'], '%Y-%m-%d').date() if request.form.get(
                'preferred_date') else None,
            preferred_time=datetime.strptime(request.form['preferred_time'], '%H:%M').time() if request.form.get(
                'preferred_time') else None,
            status=request.form.get('status', 'pending'),
            notes=request.form.get('notes', ''),
        )
        db.session.add(tr)
        db.session.commit()
        flash('تم إرسال طلب التدريب! سنتواصل معك قريباً.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('حدث خطأ أثناء إرسال الطلب.', 'error')

    # ✅ Redirect back to main, not admin
    return redirect(request.referrer or url_for('main.index'))


@admin_bp.route('/training-requests/<int:req_id>/confirm', methods=['POST'])
@login_required  # ✅ Keep this (admin only)
def confirm_training(req_id):
    from app.models.main import TrainingRequest
    tr = TrainingRequest.query.get_or_404(req_id)
    tr.status = 'confirmed'
    db.session.commit()
    flash('تم تأكيد طلب التدريب.', 'success')
    return redirect(url_for('admin.training_requests'))


@admin_bp.route('/training-requests/<int:req_id>/cancel', methods=['POST'])
@login_required  # ✅ Keep this (admin only)
def cancel_training(req_id):
    from app.models.main import TrainingRequest
    tr = TrainingRequest.query.get_or_404(req_id)
    tr.status = 'cancelled'
    db.session.commit()
    flash('تم إلغاء طلب التدريب.', 'success')
    return redirect(url_for('admin.training_requests'))


@admin_bp.route('/courts/new', methods=['GET', 'POST'])
@login_required
def new_court():
    if request.method == 'POST':
        img = save_upload(request.files.get('image'))
        court = Court(
            name=request.form['name'],
            price_per_hour=float(request.form.get('price_per_hour', 25000)),
            color=request.form.get('color', '#1565C0'),
            description=request.form.get('description', ''),
            capacity=request.form.get('capacity') or None,
            surface_type=request.form.get('surface_type', ''),
            is_active=True,
            image=img,
        )
        db.session.add(court)
        db.session.commit()
        flash('تم إضافة الملعب بنجاح.', 'success')
        return redirect(url_for('admin.courts'))
    return render_template('admin/add_court.html')

@admin_bp.route('/categories/<int:cat_id>/edit', methods=['POST'])
@login_required
def edit_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    cat.name  = request.form.get('name', cat.name)
    cat.color = request.form.get('color', cat.color)
    db.session.commit()
    flash('تم تحديث الفئة.', 'success')
    return redirect(url_for('admin.categories'))