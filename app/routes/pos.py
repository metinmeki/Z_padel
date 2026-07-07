import json
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required
from app import db
from app.models.store import Product, Order, OrderItem

pos_bp = Blueprint('pos', __name__)


@pos_bp.route('/')
@pos_bp.route('/quick-sale')
@login_required
def quick_sale():
    products = Product.query.filter_by(is_active=True).all()
    return render_template('pos/quick_sale.html', products=products)


@pos_bp.route('/checkout', methods=['POST'])
@login_required
def checkout():
    try:
        data = request.get_json(force=True) or {}
        items = data.get('items', [])
        payment_method = data.get('payment_method', 'cash')

        if not items:
            return jsonify(success=False, message='لا توجد منتجات في الطلب'), 400

        order = Order(
            customer_name='زبون POS',
            status='completed',
            notes=payment_method,
        )
        db.session.add(order)

        total = 0
        for it in items:
            prod = Product.query.get(it.get('product_id'))
            qty = int(it.get('quantity', 0))

            if not prod or qty <= 0:
                db.session.rollback()
                return jsonify(success=False, message='منتج غير صالح'), 400

            if prod.stock < qty:
                db.session.rollback()
                return jsonify(success=False, message=f'الكمية غير متوفرة: {prod.name}'), 400

            unit_price = prod.price
            subtotal = unit_price * qty

            db.session.add(OrderItem(
                order=order,
                product_id=prod.id,
                quantity=qty,
                price=unit_price,
                subtotal=subtotal,
            ))

            prod.stock -= qty
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
        items   = data.get('items', [])
        name    = (data.get('name') or '').strip()
        phone   = (data.get('phone') or '').strip()
        note    = (data.get('note') or '').strip()

        if not name:
            return jsonify(success=False, message='الرجاء كتابة اسم الشخص'), 400
        if not items:
            return jsonify(success=False, message='لا توجد منتجات في الطلب'), 400

        notes_parts = ['دين']
        if phone:
            notes_parts.append(phone)
        if note:
            notes_parts.append(note)

        order = Order(
            customer_name=name,
            customer_phone=phone or None,
            status='pending',
            notes=' - '.join(notes_parts),
        )
        db.session.add(order)

        total = 0
        for it in items:
            prod = Product.query.get(it.get('product_id'))
            qty = int(it.get('quantity', 0))

            if not prod or qty <= 0:
                db.session.rollback()
                return jsonify(success=False, message='منتج غير صالح'), 400

            if prod.stock < qty:
                db.session.rollback()
                return jsonify(success=False, message=f'الكمية غير متوفرة: {prod.name}'), 400

            unit_price = prod.price
            subtotal = unit_price * qty

            db.session.add(OrderItem(
                order=order,
                product_id=prod.id,
                quantity=qty,
                price=unit_price,
                subtotal=subtotal,
            ))

            prod.stock -= qty
            total += subtotal

        order.total_price = total
        db.session.commit()

        return jsonify(success=True, order_id=order.id)

    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


@pos_bp.route('/sale', methods=['POST'])
@login_required
def process_sale():
    try:
        items = json.loads(request.form.get('items', '[]'))
        if not items:
            flash('لا توجد منتجات في الطلب.', 'danger')
            return redirect(url_for('pos.quick_sale'))

        order = Order(
            customer_name=request.form.get('customer_name', 'زبون'),
            status='completed',
        )
        db.session.add(order)

        total = 0
        for item in items:
            prod = Product.query.get(item['id'])
            if prod and prod.stock >= item['qty']:
                subtotal = prod.price * item['qty']
                db.session.add(OrderItem(
                    order=order,
                    product_id=prod.id,
                    quantity=item['qty'],
                    price=prod.price,
                    subtotal=subtotal,
                ))
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
    order     = Order.query.get_or_404(order_id)
    autoprint = request.args.get('autoprint', '0') == '1'
    return render_template('pos/receipt.html', order=order, autoprint=autoprint)
