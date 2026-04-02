from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required
from app.models.store import Product, Order, OrderItem
from app import db
from datetime import datetime, date, timedelta
from sqlalchemy import func

pos = Blueprint('pos', __name__, url_prefix='/pos')


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def _date_range(period):
    """Return (start, end) datetime for the given period string."""
    now   = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == 'today':
        return today, now
    elif period == 'week':
        return today - timedelta(days=today.weekday()), now
    elif period == 'month':
        return today.replace(day=1), now
    else:  # 'all'
        return datetime(2000, 1, 1), now


# ─────────────────────────────────────────────
#  QUICK SALE
# ─────────────────────────────────────────────
@pos.route('/')
@pos.route('/quick-sale')
@login_required
def quick_sale():
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    return render_template('pos/quick_sale.html', products=products)


# ─────────────────────────────────────────────
#  CHECKOUT
# ─────────────────────────────────────────────
@pos.route('/checkout', methods=['POST'])
@login_required
def checkout():
    data           = request.get_json(silent=True) or {}
    items          = data.get('items', [])
    payment_method = data.get('payment_method', 'cash')
    cust_name      = data.get('customer_name', 'زبون POS')
    cust_phone     = data.get('customer_phone', '—')

    if not items:
        return jsonify({'success': False, 'message': 'السلة فارغة'})

    try:
        total = sum(i.get('unit_price', 0) * i.get('quantity', 1) for i in items)
        order = Order(
            customer_name  = cust_name,
            customer_phone = cust_phone,
            total_price    = total,
            status         = 'done',
            source         = 'pos',
            notes          = f'دفع: {payment_method}'
        )
        db.session.add(order)
        db.session.flush()

        for item in items:
            p = Product.query.get(item.get('product_id'))
            if not p:
                continue
            db.session.add(OrderItem(
                order_id   = order.id,
                product_id = p.id,
                quantity   = item.get('quantity', 1),
                unit_price = item.get('unit_price', p.price)
            ))
            if p.stock > 0:
                p.stock = max(0, p.stock - item.get('quantity', 1))

        db.session.commit()
        return jsonify({'success': True, 'order_id': order.id})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


# ─────────────────────────────────────────────
#  DEBT
# ─────────────────────────────────────────────
@pos.route('/debt', methods=['POST'])
@login_required
def debt():
    data  = request.get_json(silent=True) or {}
    name  = data.get('name', '').strip()
    phone = data.get('phone', '').strip()
    note  = data.get('note', '').strip()
    items = data.get('items', [])

    if not name:
        return jsonify({'success': False, 'message': 'الاسم مطلوب'})
    if not items:
        return jsonify({'success': False, 'message': 'السلة فارغة'})

    try:
        total = sum(i.get('unit_price', 0) * i.get('quantity', 1) for i in items)
        order = Order(
            customer_name  = name,
            customer_phone = phone or '—',
            total_price    = total,
            status         = 'pending',
            source         = 'pos',
            notes          = f'دين | {note}' if note else 'دين'
        )
        db.session.add(order)
        db.session.flush()

        for item in items:
            p = Product.query.get(item.get('product_id'))
            if not p:
                continue
            db.session.add(OrderItem(
                order_id   = order.id,
                product_id = p.id,
                quantity   = item.get('quantity', 1),
                unit_price = item.get('unit_price', p.price)
            ))

        db.session.commit()
        return jsonify({'success': True, 'order_id': order.id})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


# ─────────────────────────────────────────────
#  RECEIPT
# ─────────────────────────────────────────────
@pos.route('/receipt/<int:order_id>')
@login_required
def receipt(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template('pos/receipt.html', order=order)


# ─────────────────────────────────────────────
#  REPORTS
# ─────────────────────────────────────────────
@pos.route('/reports')
@login_required
def reports():
    period = request.args.get('period', 'today')
    start, end = _date_range(period)

    period_labels = {
        'today': 'اليوم',
        'week':  'هذا الأسبوع',
        'month': 'هذا الشهر',
        'all':   'كل الوقت',
    }

    # Base query — POS done orders only
    base = Order.query.filter(
        Order.source     == 'pos',
        Order.status     == 'done',
        Order.created_at >= start,
        Order.created_at <= end
    )

    all_orders = base.order_by(Order.created_at.desc()).all()

    # ── Stats ──
    revenue    = sum(o.total_price for o in all_orders)
    items_sold = sum(sum(i.quantity for i in o.items) for o in all_orders)
    avg_order  = (revenue / len(all_orders)) if all_orders else 0

    stats = {
        'revenue':    revenue,
        'orders':     len(all_orders),
        'items_sold': items_sold,
        'avg_order':  avg_order,
    }

    # ── Top products ──
    product_sales = {}
    for o in all_orders:
        for item in o.items:
            pid = item.product_id
            if pid not in product_sales:
                product_sales[pid] = {'name': item.product.name, 'qty': 0, 'total': 0}
            product_sales[pid]['qty']   += item.quantity
            product_sales[pid]['total'] += item.unit_price * item.quantity

    top_products = sorted(product_sales.values(), key=lambda x: x['qty'], reverse=True)[:10]
    max_qty = top_products[0]['qty'] if top_products else 1
    for p in top_products:
        p['pct'] = round(p['qty'] / max_qty * 100)

    # ── Payment methods ──
    pay_agg = {}
    for o in all_orders:
        method = 'cash'
        if o.notes:
            if 'card' in o.notes:   method = 'card'
            elif 'دين' in o.notes:  method = 'debt'
        if method not in pay_agg:
            pay_agg[method] = {'method': method, 'count': 0, 'total': 0}
        pay_agg[method]['count'] += 1
        pay_agg[method]['total'] += o.total_price
    pay_methods = sorted(pay_agg.values(), key=lambda x: x['total'], reverse=True)

    # ── Peak hours ──
    hour_agg = {}
    for o in all_orders:
        h = o.created_at.hour
        hour_agg[h] = hour_agg.get(h, 0) + 1
    max_h = max(hour_agg.values(), default=1)
    peak_hours = [
        {'hour': str(h).zfill(2), 'count': c, 'pct': round(c / max_h * 100)}
        for h, c in sorted(hour_agg.items(), key=lambda x: x[1], reverse=True)[:8]
    ]

    # ── Recent orders (last 20) ──
    recent_orders = all_orders[:20]

    return render_template(
        'pos/reports.html',
        period       = period,
        period_label = period_labels.get(period, ''),
        stats        = stats,
        top_products = top_products,
        pay_methods  = pay_methods,
        peak_hours   = peak_hours,
        recent_orders= recent_orders,
    )


# ─────────────────────────────────────────────
#  NOTIFICATIONS API  (used by admin sidebar)
# ─────────────────────────────────────────────
@pos.route('/api/notifications')
@login_required
def notifications_api():
    """Return unread counts for admin notification bell."""
    from app.models.main import Booking

    # Pending bookings (website + tapane)
    pending_bookings = Booking.query.filter_by(status='pending').count()

    # Cancel requests
    cancel_requests = Booking.query.filter_by(status='pending_cancel').count()

    # POS debts unpaid
    pos_debts = Order.query.filter_by(source='pos', status='pending').count()

    # Website orders pending
    website_orders = Order.query.filter_by(source='website', status='pending').count()

    total = pending_bookings + cancel_requests + pos_debts + website_orders

    return jsonify({
        'total':           total,
        'pending_bookings': pending_bookings,
        'cancel_requests':  cancel_requests,
        'pos_debts':        pos_debts,
        'website_orders':   website_orders,
    })