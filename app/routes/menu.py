import os
import secrets
import threading
from datetime import datetime, date
from functools import wraps

from flask import (Blueprint, render_template, request, redirect, url_for, flash, g, session,
                   jsonify, current_app)
from flask_login import login_required, current_user

from app import db
from app.models.store import Category, Product, Order, OrderItem, MenuOrder, MenuOrderItem
from app.models.main import (Court, ActivityTable, ACTIVITY_META, CourtSession, CourtSessionItem,
                             ActivitySession, ActivitySessionItem, ActivityLog)

menu_bp = Blueprint('menu', __name__)

# The café menu is published on its own subdomain; everything else lives on the main site.
MENU_HOST = os.environ.get('MENU_HOST', 'menu.z-padel.com').lower()
MAIN_URL  = os.environ.get('MAIN_URL', 'https://z-padel.com').rstrip('/')

# Endpoints that may be used on the menu subdomain (everything else redirects to the main site)
MENU_HOST_ENDPOINTS = ('main.set_lang', 'menu.public_menu', 'menu.place_order', 'menu.order_status')

# Activity tables customers can order to (besides courts and the counter)
ORDER_TABLE_ACTIVITIES = ('snooker', 'billiard')

MAX_OPEN_ORDERS = 3      # pending orders one phone can have at once
MAX_LINES, MAX_QTY = 30, 20


def is_menu_host():
    return (request.host or '').split(':')[0].lower() == MENU_HOST


def _localized(obj, lang):
    if lang == 'ar' and obj.name_ar:
        return obj.name_ar
    if lang == 'ku' and (obj.name_ku or obj.name_ar):
        return obj.name_ku or obj.name_ar
    return obj.name


def _description(p, lang):
    if lang == 'ar':
        return p.description_ar or p.description
    if lang == 'ku':
        return p.description_ku or p.description_ar or p.description
    return p.description


def menu_sections(lang):
    """[(category, display name, [(product, name, description)])] for categories shown on the menu."""
    cats = Category.query.filter_by(show_on_menu=True).order_by(Category.name).all()
    sections = []
    for c in cats:
        items = (Product.query.filter_by(category_id=c.id, is_active=True, show_on_menu=True)
                 .order_by(Product.name).all())
        if items:
            sections.append((c, _localized(c, lang),
                             [(p, _localized(p, lang), _description(p, lang)) for p in items]))
    return sections


# ── Places customers can order to ──
def all_places(lang='en'):
    """[(code, label, kind)] — courts first, then snooker / billiard tables. Everyone else orders to the counter."""
    places = [(f'court-{c.id}', c.name, 'court')
              for c in Court.query.filter_by(is_active=True).order_by(Court.name).all()]
    tables = (ActivityTable.query.filter(ActivityTable.is_active == True,  # noqa: E712
                                         ActivityTable.activity.in_(ORDER_TABLE_ACTIVITIES))
              .order_by(ActivityTable.activity.desc(), ActivityTable.name).all())
    for tb in tables:
        meta = ACTIVITY_META.get(tb.activity, {})
        places.append((f'table-{tb.id}', f"{meta.get('en' if lang == 'en' else 'ar', tb.activity)} – {tb.name}", tb.activity))
    return places


def parse_place(code, lang='en'):
    """'court-3' / 'table-5' / 'counter' -> (type, id, label), or None if unknown."""
    if code == 'counter':
        return ('counter', None, 'Counter')
    for c, label, kind in all_places(lang):
        if c == code:
            kind_type, _, pid = code.partition('-')
            return (kind_type, int(pid), label)
    return None


def _orderable(p):
    return (p and p.is_active and p.show_on_menu and p.category and p.category.show_on_menu
            and (p.stock or 0) > 0)


# ═══════════════════════════════════════════
# PUBLIC  (menu.z-padel.com/, and /menu/ on the main site as a preview)
# ═══════════════════════════════════════════
@menu_bp.route('/menu/')
def public_menu():
    at = request.args.get('at')
    if at and parse_place(at):
        session['menu_place'] = at                 # remembered from the court/table QR code
    place = parse_place(session.get('menu_place', ''), g.lang) if session.get('menu_place') else None
    resp = render_template('menu/public.html', sections=menu_sections(g.lang),
                           main_url=MAIN_URL if is_menu_host() else '',
                           place_code=session.get('menu_place') if place else None,
                           place_label=place[2] if place else None,
                           places=all_places(g.lang))
    return resp, 200, {'Cache-Control': 'no-cache'}


def _notify_barista(app, title, body):
    def run():
        with app.app_context():
            try:
                from app.routes.admin import _send_push_all
                _send_push_all(title, body, '/pos/orders')
            except Exception:
                current_app.logger.exception('menu order push failed')
    threading.Thread(target=run, daemon=True).start()


@menu_bp.route('/menu/order', methods=['POST'])
def place_order():
    data = request.get_json(silent=True) or {}
    place = parse_place(str(data.get('place') or ''), 'en')
    name = (str(data.get('name') or '')).strip()[:80]
    note = (str(data.get('note') or '')).strip()[:300]
    lines = data.get('items') if isinstance(data.get('items'), list) else []

    if not place:
        return jsonify(ok=False, error='place'), 400
    if place[0] == 'counter' and not name:
        return jsonify(ok=False, error='name'), 400
    if not lines or len(lines) > MAX_LINES:
        return jsonify(ok=False, error='empty'), 400

    mine = session.get('menu_orders', [])
    open_count = MenuOrder.query.filter(MenuOrder.code.in_(mine), MenuOrder.status == 'pending').count() if mine else 0
    if open_count >= MAX_OPEN_ORDERS:
        return jsonify(ok=False, error='too_many'), 429

    qty_by_product = {}
    for ln in lines:
        try:
            pid, qty = int(ln.get('id')), int(ln.get('qty'))
        except (TypeError, ValueError, AttributeError):
            return jsonify(ok=False, error='empty'), 400
        if qty > 0:
            qty_by_product[pid] = min(MAX_QTY, qty_by_product.get(pid, 0) + qty)
    if not qty_by_product:
        return jsonify(ok=False, error='empty'), 400

    products = {p.id: p for p in Product.query.filter(Product.id.in_(qty_by_product)).all()}
    unavailable = [pid for pid in qty_by_product if not _orderable(products.get(pid))
                   or products[pid].stock < qty_by_product[pid]]
    if unavailable:
        return jsonify(ok=False, error='unavailable',
                       items=[_localized(products[p], g.lang) if p in products else str(p) for p in unavailable]), 409

    o = MenuOrder(code=secrets.token_urlsafe(12)[:16], place_type=place[0], place_id=place[1],
                  place_label=place[2], customer_name=name or None, note=note or None, status='pending')
    total = 0
    for pid, qty in qty_by_product.items():
        p = products[pid]
        o.items.append(MenuOrderItem(product_id=p.id, product_name=p.name, price=p.price,
                                     quantity=qty, subtotal=p.price * qty))
        total += p.price * qty
    o.total = total
    db.session.add(o)
    db.session.commit()

    session['menu_orders'] = (mine + [o.code])[-10:]
    _notify_barista(current_app._get_current_object(), f'☕ New order — {o.place_label}',
                    ', '.join(f'{i.quantity}× {i.product_name}' for i in o.items)
                    + (f' — {o.customer_name}' if o.customer_name else ''))
    return jsonify(ok=True, code=o.code)


@menu_bp.route('/menu/order/<code>')
def order_status(code):
    o = MenuOrder.query.filter_by(code=code).first_or_404()
    return jsonify(status=o.status, place=o.place_label, billed_to=o.billed_to, reason=o.reject_reason,
                   total=o.total, items=[dict(name=i.product_name, qty=i.quantity) for i in o.items])


# ═══════════════════════════════════════════
# BARISTA  (POS > Orders)
# ═══════════════════════════════════════════
def _log(action, details):
    db.session.add(ActivityLog(user_id=current_user.id, username=current_user.username, action=action,
                               details=details[:300], ip_address=request.remote_addr or ''))


def _active_session(o):
    if o.place_type == 'court':
        return (CourtSession.query.filter(CourtSession.court_id == o.place_id,
                                          CourtSession.status.in_(('active', 'pending_payment')))
                .order_by(CourtSession.id.desc()).first())
    if o.place_type == 'table':
        return (ActivitySession.query.filter(ActivitySession.table_id == o.place_id,
                                             ActivitySession.status.in_(('active', 'pending_payment')))
                .order_by(ActivitySession.id.desc()).first())
    return None


@menu_bp.route('/pos/orders')
@login_required
def barista_orders():
    pending = MenuOrder.query.filter_by(status='pending').order_by(MenuOrder.created_at).all()
    collect = (MenuOrder.query.filter_by(status='accepted', billed_to='counter')
               .order_by(MenuOrder.decided_at).all())
    today_start = datetime.combine(date.today(), datetime.min.time())
    recent = (MenuOrder.query.filter(MenuOrder.status.in_(('accepted', 'rejected', 'paid', 'cancelled')),
                                     MenuOrder.decided_at >= today_start)
              .filter(~((MenuOrder.status == 'accepted') & (MenuOrder.billed_to == 'counter')))
              .order_by(MenuOrder.decided_at.desc()).limit(25).all())
    return render_template('pos/menu_orders.html', pending=pending, collect=collect, recent=recent,
                           sessions={o.id: _active_session(o) for o in pending})


@menu_bp.route('/pos/orders/count')
@login_required
def barista_orders_count():
    latest = db.session.query(db.func.max(MenuOrder.id)).filter(MenuOrder.status == 'pending').scalar() or 0
    return jsonify(pending=MenuOrder.query.filter_by(status='pending').count(),
                   collect=MenuOrder.query.filter_by(status='accepted', billed_to='counter').count(),
                   latest=latest)


@menu_bp.route('/pos/orders/<int:order_id>/accept', methods=['POST'])
@login_required
def barista_accept(order_id):
    o = MenuOrder.query.get_or_404(order_id)
    if o.status != 'pending':
        flash('هذا الطلب تمت معالجته. / This order was already handled.', 'error')
        return redirect(url_for('menu.barista_orders'))

    products = {p.id: p for p in Product.query.filter(Product.id.in_([i.product_id for i in o.items])).all()}
    short = [i.product_name for i in o.items if not products.get(i.product_id) or products[i.product_id].stock < i.quantity]
    if short:
        flash('الكمية غير متوفرة / Not enough stock: ' + ', '.join(short) + ' — reject the order or fix the stock.', 'error')
        return redirect(url_for('menu.barista_orders'))

    sess = _active_session(o)
    if sess is not None:
        item_cls = CourtSessionItem if o.place_type == 'court' else ActivitySessionItem
        for i in o.items:
            existing = item_cls.query.filter_by(session_id=sess.id, product_id=i.product_id).first()
            if existing:
                existing.quantity += i.quantity
                existing.subtotal = existing.quantity * existing.price
            else:
                db.session.add(item_cls(session_id=sess.id, product_id=i.product_id, product_name=i.product_name,
                                        quantity=i.quantity, price=i.price, subtotal=i.price * i.quantity))
        o.billed_to = 'court_session' if o.place_type == 'court' else 'activity_session'
        o.session_id = sess.id
    else:
        o.billed_to = 'counter'
    for i in o.items:
        products[i.product_id].stock -= i.quantity

    o.status, o.decided_at, o.handled_by = 'accepted', datetime.utcnow(), current_user.username
    _log('Accept Menu Order', f'#{o.id} {o.place_label} — {int(o.total):,} IQD → '
         + ('bill of ' + o.place_label if o.session_id else 'pay at counter'))
    db.session.commit()
    flash((f'✓ أضيف إلى فاتورة {o.place_label} / Added to {o.place_label} bill.' if o.session_id
           else f'✓ مقبول — الدفع عند الكاونتر / Accepted — pay at the counter ({o.customer_name or o.place_label}).'), 'success')
    return redirect(url_for('menu.barista_orders'))


@menu_bp.route('/pos/orders/<int:order_id>/reject', methods=['POST'])
@login_required
def barista_reject(order_id):
    o = MenuOrder.query.get_or_404(order_id)
    if o.status == 'pending':
        o.status, o.decided_at, o.handled_by = 'rejected', datetime.utcnow(), current_user.username
        o.reject_reason = (request.form.get('reason') or '').strip()[:200] or None
        _log('Reject Menu Order', f'#{o.id} {o.place_label}' + (f' — {o.reject_reason}' if o.reject_reason else ''))
        db.session.commit()
    return redirect(url_for('menu.barista_orders'))


@menu_bp.route('/pos/orders/<int:order_id>/paid', methods=['POST'])
@login_required
def barista_paid(order_id):
    o = MenuOrder.query.get_or_404(order_id)
    if o.status != 'accepted' or o.billed_to != 'counter':
        return redirect(url_for('menu.barista_orders'))
    method = request.form.get('method') if request.form.get('method') in ('cash', 'card') else 'cash'
    sale = Order(customer_name=o.customer_name or o.place_label or 'Menu order', status='completed', notes=method)
    for i in o.items:          # stock was already taken when the order was accepted
        sale.items.append(OrderItem(product_id=i.product_id, product_name=i.product_name,
                                    quantity=i.quantity, price=i.price, subtotal=i.subtotal))
    sale.total_price = o.total
    db.session.add(sale)
    db.session.flush()
    o.status, o.order_id = 'paid', sale.id
    _log('Menu Order Paid', f'#{o.id} {o.customer_name or o.place_label} — {int(o.total):,} IQD ({method})')
    db.session.commit()
    flash(f'✓ تم الدفع / Paid — receipt #{sale.id}', 'success')
    return redirect(url_for('menu.barista_orders'))


@menu_bp.route('/pos/orders/<int:order_id>/cancel', methods=['POST'])
@login_required
def barista_cancel(order_id):
    o = MenuOrder.query.get_or_404(order_id)
    if o.status == 'accepted' and o.billed_to == 'counter':
        for i in o.items:          # give the stock back
            p = Product.query.get(i.product_id)
            if p:
                p.stock = (p.stock or 0) + i.quantity
        o.status = 'cancelled'
        _log('Cancel Menu Order', f'#{o.id} {o.customer_name or o.place_label} — not collected')
        db.session.commit()
    return redirect(url_for('menu.barista_orders'))


# ═══════════════════════════════════════════
# ADMIN
# ═══════════════════════════════════════════
def _admin_required(f):
    @wraps(f)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.has_perm('perm_products'):
            flash('Access denied.', 'danger')
            return redirect(url_for('admin.dashboard'))
        return f(*args, **kwargs)
    return wrapper


@menu_bp.route('/admin/menu', methods=['GET', 'POST'])
@_admin_required
def admin_menu():
    categories = Category.query.order_by(Category.name).all()
    if request.method == 'POST':
        f = request.form
        for c in categories:
            c.show_on_menu = f.get(f'cat-{c.id}-show') == '1'
            c.name_ar = (f.get(f'cat-{c.id}-ar') or '').strip()[:80] or None
            c.name_ku = (f.get(f'cat-{c.id}-ku') or '').strip()[:80] or None
        for p in Product.query.filter(Product.id.in_(f.getlist('product_ids', type=int))).all():
            p.show_on_menu = f.get(f'prod-{p.id}-show') == '1'
            p.name_ar = (f.get(f'prod-{p.id}-ar') or '').strip()[:120] or None
            p.name_ku = (f.get(f'prod-{p.id}-ku') or '').strip()[:120] or None
        db.session.commit()
        flash('تم حفظ المنيو. / Menu saved.', 'success')
        return redirect(url_for('menu.admin_menu'))

    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    by_cat = {c.id: [p for p in products if p.category_id == c.id] for c in categories}
    return render_template('menu/admin.html', categories=categories, by_cat=by_cat,
                           menu_url=f'https://{MENU_HOST}', places=all_places('en'))
