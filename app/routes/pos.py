import json
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.store import Product, Category, Order, OrderItem
from app.models.main import Court, CourtSession, CourtSessionItem, ActivityTable, ActivitySession, ActivitySessionItem, ACTIVITY_META, Booking

pos_bp = Blueprint('pos', __name__)


BARISTA_CATEGORIES = {'beverage', 'cakes'}

@pos_bp.route('/')
@pos_bp.route('/quick-sale')
@login_required
def quick_sale():
    if current_user.username.lower() == 'barista':
        all_cats = Category.query.order_by(Category.name).all()
        categories = [c for c in all_cats if c.name.strip().lower() in BARISTA_CATEGORIES]
        cat_ids = [c.id for c in categories]
        products = Product.query.filter_by(is_active=True).filter(
            Product.category_id.in_(cat_ids)
        ).all()
    else:
        products   = Product.query.filter_by(is_active=True).all()
        categories = Category.query.order_by(Category.name).all()
    return render_template('pos/quick_sale.html', products=products, categories=categories)


@pos_bp.route('/checkout', methods=['POST'])
@login_required
def checkout():
    try:
        data = request.get_json(force=True) or {}
        items = data.get('items', [])
        payment_method = data.get('payment_method', 'cash')

        if not items:
            return jsonify(success=False, message='لا توجد منتجات في الطلب'), 400

        order = Order(customer_name='زبون POS', status='completed', notes=payment_method)
        db.session.add(order)

        total = 0
        for it in items:
            pid = it.get('product_id')
            qty = int(it.get('quantity', 0))
            if qty <= 0:
                continue
            if pid:
                prod = Product.query.get(pid)
                if not prod:
                    db.session.rollback()
                    return jsonify(success=False, message='منتج غير صالح'), 400
                if prod.stock < qty:
                    db.session.rollback()
                    return jsonify(success=False, message=f'الكمية غير متوفرة: {prod.name}'), 400
                unit_price = prod.price
                subtotal   = unit_price * qty
                db.session.add(OrderItem(order=order, product_id=prod.id,
                                         product_name=prod.name,
                                         quantity=qty, price=unit_price, subtotal=subtotal))
                prod.stock -= qty
            else:
                vname      = (it.get('name') or '').strip()
                unit_price = float(it.get('unit_price', 0))
                if not vname or unit_price <= 0:
                    db.session.rollback()
                    return jsonify(success=False, message='بيانات النشاط غير صحيحة'), 400
                subtotal = unit_price * qty
                db.session.add(OrderItem(order=order, product_id=None,
                                         product_name=vname,
                                         quantity=qty, price=unit_price, subtotal=subtotal))
            total += subtotal

        order.total_price = total
        db.session.commit()
        return jsonify(success=True, order_id=order.id)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


@pos_bp.route('/debt', methods=['POST'])
@login_required
def debt():
    try:
        data = request.get_json(force=True) or {}
        items = data.get('items', [])
        name = (data.get('name') or '').strip()
        phone = (data.get('phone') or '').strip()
        note = (data.get('note') or '').strip()

        if not name:
            return jsonify(success=False, message='الرجاء كتابة اسم الشخص'), 400
        if not items:
            return jsonify(success=False, message='لا توجد منتجات في الطلب'), 400

        notes_parts = ['دين']
        if phone: notes_parts.append(phone)
        if note: notes_parts.append(note)

        order = Order(customer_name=name, customer_phone=phone or None, status='pending', notes=' - '.join(notes_parts))
        db.session.add(order)

        total = 0
        for it in items:
            pid = it.get('product_id')
            qty = int(it.get('quantity', 0))
            if qty <= 0:
                continue
            if pid:
                prod = Product.query.get(pid)
                if not prod:
                    db.session.rollback()
                    return jsonify(success=False, message='منتج غير صالح'), 400
                if prod.stock < qty:
                    db.session.rollback()
                    return jsonify(success=False, message=f'الكمية غير متوفرة: {prod.name}'), 400
                unit_price = prod.price
                subtotal   = unit_price * qty
                db.session.add(OrderItem(order=order, product_id=prod.id,
                                         product_name=prod.name,
                                         quantity=qty, price=unit_price, subtotal=subtotal))
                prod.stock -= qty
            else:
                vname      = (it.get('name') or '').strip()
                unit_price = float(it.get('unit_price', 0))
                if not vname or unit_price <= 0:
                    db.session.rollback()
                    return jsonify(success=False, message='بيانات النشاط غير صحيحة'), 400
                subtotal = unit_price * qty
                db.session.add(OrderItem(order=order, product_id=None,
                                         product_name=vname,
                                         quantity=qty, price=unit_price, subtotal=subtotal))
            total += subtotal

        order.total_price = total
        db.session.commit()
        return jsonify(success=True, order_id=order.id)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


@pos_bp.route('/courts')
@login_required
def courts():
    court_list = Court.query.filter_by(is_active=True).all()
    active_sessions = {s.court_id: s for s in CourtSession.query.filter_by(status='active').all()}
    pending_court_sessions = CourtSession.query.filter_by(status='pending_payment').all()
    pending_activity_sessions = ActivitySession.query.filter_by(status='pending_payment').all()
    return render_template('pos/courts.html', courts=court_list, active_sessions=active_sessions,
                           pending_court_sessions=pending_court_sessions,
                           pending_activity_sessions=pending_activity_sessions,
                           activity_meta=ACTIVITY_META)


@pos_bp.route('/courts/<int:court_id>/start', methods=['POST'])
@login_required
def start_court_session(court_id):
    court = Court.query.get_or_404(court_id)
    existing = CourtSession.query.filter_by(court_id=court_id, status='active').first()
    if existing:
        return jsonify(success=False, message='الملعب مشغول بالفعل'), 400

    data = request.get_json(silent=True) or {}
    customer_name = (data.get('customer_name') or '').strip() or None

    if not customer_name:
        from datetime import date as date_type
        now_local = datetime.now()
        booking = Booking.query.filter_by(
            court_id=court_id,
            booking_date=now_local.date(),
            status='confirmed'
        ).filter(
            Booking.start_time <= now_local.time(),
            Booking.end_time > now_local.time()
        ).first()
        if booking:
            customer_name = booking.customer_name

    session_row = CourtSession(court_id=court.id, start_time=datetime.utcnow(), status='active', customer_name=customer_name)
    db.session.add(session_row)
    db.session.commit()

    return jsonify(success=True, session_id=session_row.id)


@pos_bp.route('/courts/session/<int:session_id>')
@login_required
def session_detail(session_id):
    session_row = CourtSession.query.get_or_404(session_id)
    if current_user.username.lower() == 'barista':
        all_cats = Category.query.order_by(Category.name).all()
        categories = [c for c in all_cats if c.name.strip().lower() in BARISTA_CATEGORIES]
        cat_ids = [c.id for c in categories]
        products = Product.query.filter_by(is_active=True).filter(
            Product.category_id.in_(cat_ids)
        ).all()
    else:
        products = Product.query.filter_by(is_active=True).all()
        categories = Category.query.all()
    # Available destinations for Move Tab
    busy_activity_ids = {s.table_id for s in ActivitySession.query.filter_by(status='active').all()}
    busy_court_ids    = {s.court_id  for s in CourtSession.query.filter_by(status='active').all()}
    free_tables = ActivityTable.query.filter_by(is_active=True).filter(
        ~ActivityTable.id.in_(busy_activity_ids)).all()
    free_courts = Court.query.filter_by(is_active=True).filter(
        ~Court.id.in_(busy_court_ids)).all()
    return render_template('pos/session_detail.html', session=session_row,
                           products=products, categories=categories,
                           free_tables=free_tables, free_courts=free_courts,
                           activity_meta=ACTIVITY_META)


@pos_bp.route('/courts/session/<int:session_id>/move', methods=['POST'])
@login_required
def move_court_session(session_id):
    sess = CourtSession.query.get_or_404(session_id)
    if sess.status != 'active':
        return jsonify(success=False, message='Session not active'), 400
    data      = request.get_json(force=True) or {}
    dest_type = data.get('dest_type')
    dest_id   = int(data.get('dest_id', 0))

    sess.end_time = datetime.utcnow()
    time_charge = sess.calc_price()
    label = f"{sess.court.name} ({sess.elapsed_minutes} min)"

    if dest_type == 'activity':
        dest = ActivityTable.query.get_or_404(dest_id)
        if ActivitySession.query.filter_by(table_id=dest_id, status='active').first():
            return jsonify(success=False, message='That table is already busy'), 400
        new_sess = ActivitySession(table_id=dest_id,
                                   customer_name=sess.customer_name,
                                   start_time=datetime.utcnow())
        db.session.add(new_sess)
        db.session.flush()
        if time_charge > 0:
            db.session.add(ActivitySessionItem(session_id=new_sess.id,
                product_name=label, quantity=1, price=time_charge, subtotal=time_charge))
        for it in sess.items:
            db.session.add(ActivitySessionItem(session_id=new_sess.id,
                product_id=it.product_id, product_name=it.product_name,
                quantity=it.quantity, price=it.price, subtotal=it.subtotal))
        sess.status = 'closed'; sess.total_price = 0
        db.session.commit()
        return jsonify(success=True, redirect=url_for('pos.activity_session', session_id=new_sess.id))

    elif dest_type == 'court':
        dest = Court.query.get_or_404(dest_id)
        if CourtSession.query.filter_by(court_id=dest_id, status='active').first():
            return jsonify(success=False, message='That court is already busy'), 400
        new_sess = CourtSession(court_id=dest_id,
                                customer_name=sess.customer_name,
                                start_time=datetime.utcnow())
        db.session.add(new_sess)
        db.session.flush()
        if time_charge > 0:
            db.session.add(CourtSessionItem(session_id=new_sess.id,
                product_name=label, quantity=1, price=time_charge, subtotal=time_charge))
        for it in sess.items:
            db.session.add(CourtSessionItem(session_id=new_sess.id,
                product_id=it.product_id, product_name=it.product_name,
                quantity=it.quantity, price=it.price, subtotal=it.subtotal))
        sess.status = 'closed'; sess.total_price = 0
        db.session.commit()
        return jsonify(success=True, redirect=url_for('pos.session_detail', session_id=new_sess.id))

    return jsonify(success=False, message='Invalid destination'), 400


@pos_bp.route('/courts/session/<int:session_id>/add-item', methods=['POST'])
@login_required
def add_session_item(session_id):
    session_row = CourtSession.query.get_or_404(session_id)
    if session_row.status != 'active':
        return jsonify(success=False, message='الجلسة غير نشطة'), 400

    data = request.get_json(force=True) or {}
    product_id = data.get('product_id')
    qty = int(data.get('quantity', 1))

    prod = Product.query.get(product_id)
    if not prod or qty <= 0:
        return jsonify(success=False, message='منتج غير صالح'), 400
    if prod.stock < qty:
        return jsonify(success=False, message=f'الكمية غير متوفرة: {prod.name}'), 400

    existing_item = CourtSessionItem.query.filter_by(session_id=session_id, product_id=prod.id).first()
    if existing_item:
        existing_item.quantity += qty
        existing_item.subtotal = existing_item.quantity * existing_item.price
    else:
        db.session.add(CourtSessionItem(
            session_id=session_id, product_id=prod.id, product_name=prod.name,
            quantity=qty, price=prod.price, subtotal=prod.price * qty,
        ))

    prod.stock -= qty
    db.session.commit()

    return jsonify(success=True, grand_total=session_row.grand_total)


@pos_bp.route('/courts/session/<int:session_id>/remove-item/<int:item_id>', methods=['POST'])
@login_required
def remove_session_item(session_id, item_id):
    item = CourtSessionItem.query.get_or_404(item_id)
    prod = Product.query.get(item.product_id)
    if prod:
        prod.stock += item.quantity
    db.session.delete(item)
    db.session.commit()

    session_row = CourtSession.query.get_or_404(session_id)
    return jsonify(success=True, grand_total=session_row.grand_total)


@pos_bp.route('/courts/session/<int:session_id>/end-time', methods=['POST'])
@login_required
def end_session_time(session_id):
    session_row = CourtSession.query.get_or_404(session_id)
    if session_row.status != 'active':
        return jsonify(success=False, message='الجلسة غير نشطة'), 400
    if session_row.end_time:
        return jsonify(success=False, message='تم إنهاء الوقت مسبقاً'), 400

    session_row.end_time = datetime.utcnow()
    session_row.total_price = session_row.calc_price()
    db.session.commit()

    return jsonify(success=True, grand_total=session_row.grand_total)


@pos_bp.route('/courts/session/<int:session_id>/free', methods=['POST'])
@login_required
def free_court_session(session_id):
    session_row = CourtSession.query.get_or_404(session_id)
    if session_row.status != 'active':
        return jsonify(success=False, message='الجلسة غير نشطة'), 400
    data = request.get_json(silent=True) or {}
    discount = max(0, float(data.get('discount', 0) or 0))
    if not session_row.end_time:
        session_row.end_time = datetime.utcnow()
        session_row.total_price = session_row.calc_price()
    if discount > 0:
        session_row.total_price = max(0, (session_row.total_price or 0) - discount)
    session_row.status = 'pending_payment'
    db.session.commit()
    return jsonify(success=True)


@pos_bp.route('/courts/session/<int:session_id>/finish', methods=['POST'])
@login_required
def finish_session(session_id):
    try:
        data = request.get_json(force=True) or {}
        payment_method = data.get('payment_method', 'cash')
        discount = max(0, float(data.get('discount', 0) or 0))

        session_row = CourtSession.query.get_or_404(session_id)
        if session_row.status == 'completed':
            return jsonify(success=False, message='تم الدفع مسبقاً'), 400

        if not session_row.end_time:
            session_row.end_time = datetime.utcnow()
            session_row.total_price = session_row.calc_price()

        if discount > 0:
            session_row.total_price = max(0, (session_row.total_price or 0) - discount)

        session_row.payment_method = payment_method
        session_row.status = 'completed'
        db.session.commit()

        return jsonify(success=True, grand_total=session_row.grand_total, session_id=session_row.id)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


@pos_bp.route('/courts/session/<int:session_id>/finish-debt', methods=['POST'])
@login_required
def finish_session_debt(session_id):
    try:
        data = request.get_json(force=True) or {}
        name = (data.get('name') or '').strip()

        if not name:
            return jsonify(success=False, message='الرجاء كتابة اسم الشخص'), 400

        session_row = CourtSession.query.get_or_404(session_id)
        if session_row.status == 'completed':
            return jsonify(success=False, message='تم الدفع مسبقاً'), 400

        if not session_row.end_time:
            session_row.end_time = datetime.utcnow()
            session_row.total_price = session_row.calc_price()

        session_row.customer_name = name
        session_row.payment_method = 'debt'
        session_row.status = 'completed'
        db.session.commit()

        return jsonify(success=True, grand_total=session_row.grand_total, session_id=session_row.id)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


@pos_bp.route('/courts/session/<int:session_id>/cancel', methods=['POST'])
@login_required
def cancel_court_session(session_id):
    session_row = CourtSession.query.get_or_404(session_id)
    if session_row.status == 'completed':
        return jsonify(success=False, message='لا يمكن الإلغاء بعد الدفع'), 400

    for item in session_row.items:
        prod = Product.query.get(item.product_id)
        if prod:
            prod.stock += item.quantity

    db.session.delete(session_row)
    db.session.commit()
    return jsonify(success=True)


@pos_bp.route('/sale', methods=['POST'])
@login_required
def process_sale():
    try:
        items = json.loads(request.form.get('items', '[]'))
        if not items:
            flash('لا توجد منتجات في الطلب.', 'danger')
            return redirect(url_for('pos.quick_sale'))

        order = Order(customer_name=request.form.get('customer_name', 'زبون'), status='completed')
        db.session.add(order)

        total = 0
        for item in items:
            prod = Product.query.get(item['id'])
            if prod and prod.stock >= item['qty']:
                subtotal = prod.price * item['qty']
                db.session.add(OrderItem(order=order, product_id=prod.id, quantity=item['qty'], price=prod.price, subtotal=subtotal))
                prod.stock -= item['qty']
                total += subtotal

        order.total_price = total
        db.session.commit()
        return redirect(url_for('pos.receipt', order_id=order.id) + '?autoprint=1')
    except Exception as e:
        db.session.rollback()
        flash(f'خطأ: {e}', 'danger')
        return redirect(url_for('pos.quick_sale'))


@pos_bp.route('/receipt/<int:order_id>')
@login_required
def receipt(order_id):
    order = Order.query.get_or_404(order_id)
    autoprint = request.args.get('autoprint', '0') == '1'
    return render_template('pos/receipt.html', order=order, autoprint=autoprint)


@pos_bp.route('/courts/session/<int:session_id>/receipt')
@login_required
def session_receipt(session_id):
    session_row = CourtSession.query.get_or_404(session_id)
    autoprint = request.args.get('autoprint', '0') == '1'
    return render_template('pos/session_receipt.html', session=session_row, autoprint=autoprint)


# ══════════════════════════════════════════════════════
#  ACTIVITY SESSIONS  (Snooker / Billiard / Table Tennis)
# ══════════════════════════════════════════════════════

@pos_bp.route('/activities')
@login_required
def activities():
    tables = ActivityTable.query.filter_by(is_active=True).order_by(
        ActivityTable.activity, ActivityTable.name).all()
    active_sessions = {s.table_id: s for s in ActivitySession.query.filter_by(status='active').all()}
    return render_template('pos/activities.html',
                           tables=tables,
                           active_sessions=active_sessions,
                           activity_meta=ACTIVITY_META,
                           activities_order=['snooker', 'billiard', 'table_tennis'])


@pos_bp.route('/activities/table/<int:table_id>/start', methods=['POST'])
@login_required
def start_activity_session(table_id):
    table = ActivityTable.query.get_or_404(table_id)
    existing = ActivitySession.query.filter_by(table_id=table_id, status='active').first()
    if existing:
        return jsonify(success=False, message='Table is already in use'), 400
    data = request.get_json(silent=True) or {}
    customer_name = (data.get('customer_name') or '').strip() or None
    sess = ActivitySession(table_id=table.id, start_time=datetime.utcnow(), customer_name=customer_name)
    db.session.add(sess)
    db.session.commit()
    return jsonify(success=True, session_id=sess.id)


@pos_bp.route('/activities/session/<int:session_id>')
@login_required
def activity_session(session_id):
    sess = ActivitySession.query.get_or_404(session_id)
    if current_user.username.lower() == 'barista':
        all_cats = Category.query.order_by(Category.name).all()
        categories = [c for c in all_cats if c.name.strip().lower() in BARISTA_CATEGORIES]
        cat_ids = [c.id for c in categories]
        products = Product.query.filter_by(is_active=True).filter(
            Product.category_id.in_(cat_ids)
        ).all()
    else:
        products   = Product.query.filter_by(is_active=True).all()
        categories = Category.query.all()
    # Available destinations for Move Tab
    busy_activity_ids = {s.table_id for s in ActivitySession.query.filter_by(status='active').all()}
    busy_court_ids    = {s.court_id  for s in CourtSession.query.filter_by(status='active').all()}
    free_tables = ActivityTable.query.filter_by(is_active=True).filter(
        ~ActivityTable.id.in_(busy_activity_ids)).all()
    free_courts = Court.query.filter_by(is_active=True).filter(
        ~Court.id.in_(busy_court_ids)).all()
    return render_template('pos/activity_session.html', session=sess,
                           activity_meta=ACTIVITY_META,
                           products=products, categories=categories,
                           free_tables=free_tables, free_courts=free_courts)


@pos_bp.route('/activities/session/<int:session_id>/move', methods=['POST'])
@login_required
def move_activity_session(session_id):
    sess = ActivitySession.query.get_or_404(session_id)
    if sess.status != 'active':
        return jsonify(success=False, message='Session not active'), 400
    data     = request.get_json(force=True) or {}
    dest_type = data.get('dest_type')   # 'activity' or 'court'
    dest_id   = int(data.get('dest_id', 0))

    # Lock time on current session
    sess.end_time = datetime.utcnow()
    time_charge = sess.calc_price()
    label = f"{sess.table.name} ({sess.elapsed_minutes} min)"

    if dest_type == 'activity':
        dest = ActivityTable.query.get_or_404(dest_id)
        if ActivitySession.query.filter_by(table_id=dest_id, status='active').first():
            return jsonify(success=False, message='That table is already busy'), 400
        new_sess = ActivitySession(table_id=dest_id,
                                   customer_name=sess.customer_name,
                                   start_time=datetime.utcnow())
        db.session.add(new_sess)
        db.session.flush()
        # Previous time charge as line item
        if time_charge > 0:
            db.session.add(ActivitySessionItem(session_id=new_sess.id,
                product_name=label, quantity=1, price=time_charge, subtotal=time_charge))
        # Transfer products
        for it in sess.items:
            db.session.add(ActivitySessionItem(session_id=new_sess.id,
                product_id=it.product_id, product_name=it.product_name,
                quantity=it.quantity, price=it.price, subtotal=it.subtotal))
        sess.status = 'closed'; sess.total_price = 0
        db.session.commit()
        return jsonify(success=True, redirect=url_for('pos.activity_session', session_id=new_sess.id))

    elif dest_type == 'court':
        dest = Court.query.get_or_404(dest_id)
        if CourtSession.query.filter_by(court_id=dest_id, status='active').first():
            return jsonify(success=False, message='That court is already busy'), 400
        new_sess = CourtSession(court_id=dest_id,
                                customer_name=sess.customer_name,
                                start_time=datetime.utcnow())
        db.session.add(new_sess)
        db.session.flush()
        if time_charge > 0:
            db.session.add(CourtSessionItem(session_id=new_sess.id,
                product_name=label, quantity=1, price=time_charge, subtotal=time_charge))
        for it in sess.items:
            db.session.add(CourtSessionItem(session_id=new_sess.id,
                product_id=it.product_id, product_name=it.product_name,
                quantity=it.quantity, price=it.price, subtotal=it.subtotal))
        sess.status = 'closed'; sess.total_price = 0
        db.session.commit()
        return jsonify(success=True, redirect=url_for('pos.session_detail', session_id=new_sess.id))

    return jsonify(success=False, message='Invalid destination'), 400


@pos_bp.route('/activities/session/<int:session_id>/end-time', methods=['POST'])
@login_required
def end_activity_time(session_id):
    sess = ActivitySession.query.get_or_404(session_id)
    if sess.status != 'active':
        return jsonify(success=False, message='Session not active'), 400
    if sess.end_time:
        return jsonify(success=False, message='End time already set'), 400
    sess.end_time = datetime.utcnow()
    sess.total_price = sess.calc_price()
    db.session.commit()
    return jsonify(success=True, total=sess.total_price, elapsed=sess.elapsed_seconds)


@pos_bp.route('/activities/session/<int:session_id>/free', methods=['POST'])
@login_required
def free_activity_session(session_id):
    sess = ActivitySession.query.get_or_404(session_id)
    if sess.status != 'active':
        return jsonify(success=False, message='الجلسة غير نشطة'), 400
    data = request.get_json(silent=True) or {}
    discount = max(0, float(data.get('discount', 0) or 0))
    if not sess.end_time:
        sess.end_time = datetime.utcnow()
        sess.total_price = sess.calc_price()
    if discount > 0:
        sess.total_price = max(0, (sess.total_price or 0) - discount)
    sess.status = 'pending_payment'
    db.session.commit()
    return jsonify(success=True)


@pos_bp.route('/activities/session/<int:session_id>/finish', methods=['POST'])
@login_required
def finish_activity_session(session_id):
    try:
        data = request.get_json(force=True) or {}
        payment_method = data.get('payment_method', 'cash')
        discount = max(0, float(data.get('discount', 0) or 0))
        sess = ActivitySession.query.get_or_404(session_id)
        if sess.status == 'completed':
            return jsonify(success=False, message='Already paid'), 400
        if not sess.end_time:
            sess.end_time = datetime.utcnow()
            sess.total_price = sess.calc_price()
        if discount > 0:
            sess.total_price = max(0, (sess.total_price or 0) - discount)
        sess.payment_method = payment_method
        sess.status = 'completed'
        db.session.commit()
        return jsonify(success=True, session_id=sess.id)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


@pos_bp.route('/activities/session/<int:session_id>/cancel', methods=['POST'])
@login_required
def cancel_activity_session(session_id):
    sess = ActivitySession.query.get_or_404(session_id)
    if sess.status == 'completed':
        return jsonify(success=False, message='Cannot cancel a paid session'), 400
    db.session.delete(sess)
    db.session.commit()
    return jsonify(success=True)


@pos_bp.route('/activities/session/<int:session_id>/add-item', methods=['POST'])
@login_required
def add_activity_item(session_id):
    sess = ActivitySession.query.get_or_404(session_id)
    if sess.status != 'active':
        return jsonify(success=False, message='Session not active'), 400
    data = request.get_json(force=True) or {}
    product_id = data.get('product_id')
    qty = int(data.get('quantity', 1))
    prod = Product.query.get(product_id)
    if not prod or qty <= 0:
        return jsonify(success=False, message='Invalid product'), 400
    if prod.stock < qty:
        return jsonify(success=False, message=f'Stock unavailable: {prod.name}'), 400
    existing = ActivitySessionItem.query.filter_by(session_id=session_id, product_id=prod.id).first()
    if existing:
        existing.quantity += qty
        existing.subtotal  = existing.quantity * existing.price
    else:
        db.session.add(ActivitySessionItem(
            session_id=session_id, product_id=prod.id, product_name=prod.name,
            quantity=qty, price=prod.price, subtotal=prod.price * qty))
    prod.stock -= qty
    db.session.commit()
    return jsonify(success=True, grand_total=sess.grand_total)


@pos_bp.route('/activities/session/<int:session_id>/remove-item/<int:item_id>', methods=['POST'])
@login_required
def remove_activity_item(session_id, item_id):
    item = ActivitySessionItem.query.get_or_404(item_id)
    prod = Product.query.get(item.product_id)
    if prod:
        prod.stock += item.quantity
    db.session.delete(item)
    db.session.commit()
    sess = ActivitySession.query.get_or_404(session_id)
    return jsonify(success=True, grand_total=sess.grand_total)


@pos_bp.route('/activities/session/<int:session_id>/finish-debt', methods=['POST'])
@login_required
def finish_activity_session_debt(session_id):
    try:
        data = request.get_json(force=True) or {}
        name = (data.get('name') or '').strip()
        if not name:
            return jsonify(success=False, message='Please enter name'), 400
        sess = ActivitySession.query.get_or_404(session_id)
        if sess.status == 'completed':
            return jsonify(success=False, message='Already paid'), 400
        if not sess.end_time:
            sess.end_time    = datetime.utcnow()
            sess.total_price = sess.calc_price()
        sess.customer_name  = name
        sess.payment_method = 'debt'
        sess.status         = 'completed'
        db.session.commit()
        return jsonify(success=True, session_id=sess.id)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


@pos_bp.route('/activities/session/<int:session_id>/receipt')
@login_required
def activity_receipt(session_id):
    sess = ActivitySession.query.get_or_404(session_id)
    autoprint = request.args.get('autoprint', '0') == '1'
    return render_template('pos/activity_receipt.html', session=sess,
                           activity_meta=ACTIVITY_META, autoprint=autoprint)


@pos_bp.route('/combined-checkout', methods=['POST'])
@login_required
def combined_checkout():
    try:
        data = request.get_json(force=True) or {}
        court_ids    = data.get('court_ids', [])
        activity_ids = data.get('activity_ids', [])
        payment_method = data.get('payment_method', 'cash')
        debt_name = (data.get('debt_name') or '').strip()
        discount = max(0, float(data.get('discount', 0) or 0))

        if payment_method == 'debt' and not debt_name:
            return jsonify(success=False, message='الرجاء كتابة اسم الشخص'), 400

        done_court_ids, done_activity_ids = [], []

        # Spread discount proportionally across sessions
        all_sessions_count = len(court_ids) + len(activity_ids)
        discount_per_session = round(discount / all_sessions_count) if all_sessions_count else 0

        for sid in court_ids:
            s = CourtSession.query.get(int(sid))
            if s and s.status in ('active', 'pending_payment'):
                if not s.end_time:
                    s.end_time = datetime.utcnow()
                    s.total_price = s.calc_price()
                if discount_per_session > 0:
                    s.total_price = max(0, (s.total_price or 0) - discount_per_session)
                s.payment_method = payment_method
                s.status = 'completed'
                if debt_name:
                    s.customer_name = debt_name
                done_court_ids.append(s.id)

        for sid in activity_ids:
            s = ActivitySession.query.get(int(sid))
            if s and s.status in ('active', 'pending_payment'):
                if not s.end_time:
                    s.end_time = datetime.utcnow()
                    s.total_price = s.calc_price()
                if discount_per_session > 0:
                    s.total_price = max(0, (s.total_price or 0) - discount_per_session)
                s.payment_method = payment_method
                s.status = 'completed'
                if debt_name:
                    s.customer_name = debt_name
                done_activity_ids.append(s.id)

        db.session.commit()
        c_param = ','.join(str(i) for i in done_court_ids)
        a_param = ','.join(str(i) for i in done_activity_ids)
        return jsonify(success=True, redirect=url_for('pos.combined_receipt',
                                                       court_ids=c_param, activity_ids=a_param,
                                                       autoprint='1'))
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


@pos_bp.route('/combined-receipt')
@login_required
def combined_receipt():
    c_ids = [int(x) for x in request.args.get('court_ids', '').split(',') if x.strip()]
    a_ids = [int(x) for x in request.args.get('activity_ids', '').split(',') if x.strip()]
    court_sessions    = [CourtSession.query.get(i) for i in c_ids]
    activity_sessions = [ActivitySession.query.get(i) for i in a_ids]
    court_sessions    = [s for s in court_sessions if s]
    activity_sessions = [s for s in activity_sessions if s]
    autoprint = request.args.get('autoprint', '0') == '1'
    grand_total = sum(s.grand_total for s in court_sessions) + sum(s.grand_total for s in activity_sessions)
    return render_template('pos/combined_receipt.html',
                           court_sessions=court_sessions,
                           activity_sessions=activity_sessions,
                           grand_total=grand_total,
                           activity_meta=ACTIVITY_META,
                           autoprint=autoprint)
