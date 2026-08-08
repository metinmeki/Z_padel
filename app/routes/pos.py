import json
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.store import Product, Category, Order, OrderItem
from app.models.main import Court, CourtSession, CourtSessionItem, ActivityTable, ActivitySession, ActivitySessionItem, ACTIVITY_META

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
    return render_template('pos/courts.html', courts=court_list, active_sessions=active_sessions)


@pos_bp.route('/courts/<int:court_id>/start', methods=['POST'])
@login_required
def start_court_session(court_id):
    court = Court.query.get_or_404(court_id)
    existing = CourtSession.query.filter_by(court_id=court_id, status='active').first()
    if existing:
        return jsonify(success=False, message='الملعب مشغول بالفعل'), 400

    data = request.get_json(silent=True) or {}
    customer_name = (data.get('customer_name') or '').strip() or None

    session_row = CourtSession(court_id=court.id, start_time=datetime.utcnow(), status='active', customer_name=customer_name)
    db.session.add(session_row)
    db.session.commit()

    return jsonify(success=True, session_id=session_row.id)


@pos_bp.route('/courts/session/<int:session_id>')
@login_required
def session_detail(session_id):
    session_row = CourtSession.query.get_or_404(session_id)
    products = Product.query.filter_by(is_active=True).all()
    categories = Category.query.all()
    return render_template('pos/session_detail.html', session=session_row, products=products, categories=categories)


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


@pos_bp.route('/courts/session/<int:session_id>/finish', methods=['POST'])
@login_required
def finish_session(session_id):
    try:
        data = request.get_json(force=True) or {}
        payment_method = data.get('payment_method', 'cash')

        session_row = CourtSession.query.get_or_404(session_id)
        if session_row.status == 'completed':
            return jsonify(success=False, message='تم الدفع مسبقاً'), 400

        if not session_row.end_time:
            session_row.end_time = datetime.utcnow()
            session_row.total_price = session_row.calc_price()

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
    products   = Product.query.filter_by(is_active=True).all()
    categories = Category.query.all()
    return render_template('pos/activity_session.html', session=sess,
                           activity_meta=ACTIVITY_META,
                           products=products, categories=categories)


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


@pos_bp.route('/activities/session/<int:session_id>/finish', methods=['POST'])
@login_required
def finish_activity_session(session_id):
    try:
        data = request.get_json(force=True) or {}
        payment_method = data.get('payment_method', 'cash')
        sess = ActivitySession.query.get_or_404(session_id)
        if sess.status == 'completed':
            return jsonify(success=False, message='Already paid'), 400
        if not sess.end_time:
            sess.end_time = datetime.utcnow()
            sess.total_price = sess.calc_price()
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
