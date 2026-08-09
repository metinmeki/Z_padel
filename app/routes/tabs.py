from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required
from app import db
from app.models.main import Tab, TabItem, ActivityTable, Court, ACTIVITY_META
from app.models.store import Product

tabs_bp = Blueprint('tabs', __name__)


def _finalize_location_charge(tab):
    """Add a time TabItem for the current location and return the amount (or 0)."""
    if not tab.location_since or not tab.hourly_rate:
        return 0
    minutes = tab.time_minutes
    if minutes <= 0:
        return 0
    charge = tab.time_charge
    item = TabItem(
        tab_id=tab.id,
        item_type='time',
        description=f"{tab.location_name} – {minutes} min",
        quantity=minutes,
        price=round(tab.hourly_rate / 60, 4),
        subtotal=charge,
    )
    db.session.add(item)
    return charge


def _location_info(loc_type, loc_id):
    """Return (name, hourly_rate) for a given location."""
    if loc_type == 'activity' and loc_id:
        tbl = ActivityTable.query.get(loc_id)
        if tbl:
            return tbl.name, tbl.hourly_rate
    elif loc_type == 'court' and loc_id:
        court = Court.query.get(loc_id)
        if court:
            return court.name, court.price_per_hour
    return None, None


def _is_occupied(loc_type, loc_id, exclude_tab_id=None):
    q = Tab.query.filter_by(location_type=loc_type, location_id=loc_id, status='open')
    if exclude_tab_id:
        q = q.filter(Tab.id != exclude_tab_id)
    return q.first() is not None


# ─────────────────────────────────────────────
@tabs_bp.route('/')
@login_required
def index():
    activity_tables = ActivityTable.query.filter_by(is_active=True).order_by(
        ActivityTable.activity, ActivityTable.name).all()
    courts = Court.query.filter_by(is_active=True).order_by(Court.name).all()
    open_tabs = Tab.query.filter_by(status='open').order_by(Tab.created_at).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()

    tab_map = {}
    for t in open_tabs:
        if t.location_type and t.location_id:
            tab_map[f"{t.location_type}:{t.location_id}"] = t

    selected_tab_id = request.args.get('tab', type=int)
    selected_tab = Tab.query.get(selected_tab_id) if selected_tab_id else None

    return render_template('pos/tabs.html',
        activity_tables=activity_tables,
        courts=courts,
        open_tabs=open_tabs,
        tab_map=tab_map,
        products=products,
        selected_tab=selected_tab,
        activity_meta=ACTIVITY_META,
    )


@tabs_bp.route('/open', methods=['POST'])
@login_required
def open_tab():
    name = request.form.get('customer_name', '').strip()
    loc_type = request.form.get('location_type') or None
    loc_id = request.form.get('location_id', type=int)
    if not name:
        flash('Customer name is required.', 'danger')
        return redirect(url_for('tabs.index'))

    if loc_type and loc_id and _is_occupied(loc_type, loc_id):
        flash('That location already has an active tab.', 'warning')
        return redirect(url_for('tabs.index'))

    loc_name, rate = _location_info(loc_type, loc_id)
    tab = Tab(
        customer_name=name,
        location_type=loc_type,
        location_id=loc_id,
        location_name=loc_name,
        location_since=datetime.utcnow() if loc_type else None,
        hourly_rate=rate,
    )
    db.session.add(tab)
    db.session.commit()
    return redirect(url_for('tabs.index', tab=tab.id))


@tabs_bp.route('/<int:tab_id>/move', methods=['POST'])
@login_required
def move_tab(tab_id):
    tab = Tab.query.get_or_404(tab_id)
    new_type = request.form.get('location_type') or None
    new_id = request.form.get('location_id', type=int)

    if new_type and new_id and _is_occupied(new_type, new_id, exclude_tab_id=tab_id):
        flash('That location already has an active tab.', 'warning')
        return redirect(url_for('tabs.index', tab=tab_id))

    _finalize_location_charge(tab)

    loc_name, rate = _location_info(new_type, new_id)
    tab.location_type = new_type
    tab.location_id = new_id if new_id else None
    tab.location_name = loc_name
    tab.location_since = datetime.utcnow() if new_type else None
    tab.hourly_rate = rate
    db.session.commit()
    return redirect(url_for('tabs.index', tab=tab_id))


@tabs_bp.route('/<int:tab_id>/add-item', methods=['POST'])
@login_required
def add_item(tab_id):
    tab = Tab.query.get_or_404(tab_id)
    product_id = request.form.get('product_id', type=int)
    qty = max(1, request.form.get('qty', 1, type=int))

    if product_id:
        product = Product.query.get_or_404(product_id)
        item = TabItem(
            tab_id=tab_id,
            product_id=product_id,
            item_type='product',
            description=product.name,
            quantity=qty,
            price=product.price,
            subtotal=product.price * qty,
        )
        db.session.add(item)
        db.session.commit()
    return redirect(url_for('tabs.index', tab=tab_id))


@tabs_bp.route('/<int:tab_id>/remove-item/<int:item_id>', methods=['POST'])
@login_required
def remove_item(tab_id, item_id):
    item = TabItem.query.filter_by(id=item_id, tab_id=tab_id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for('tabs.index', tab=tab_id))


@tabs_bp.route('/<int:tab_id>/close', methods=['POST'])
@login_required
def close_tab(tab_id):
    tab = Tab.query.get_or_404(tab_id)
    payment = request.form.get('payment_method', 'cash')
    _finalize_location_charge(tab)
    tab.status = 'paid'
    tab.payment_method = payment
    tab.closed_at = datetime.utcnow()
    tab.location_type = None
    tab.location_id = None
    tab.location_since = None
    tab.hourly_rate = None
    db.session.commit()
    return redirect(url_for('tabs.receipt', tab_id=tab_id))


@tabs_bp.route('/<int:tab_id>/receipt')
@login_required
def receipt(tab_id):
    tab = Tab.query.get_or_404(tab_id)
    return render_template('pos/tab_receipt.html', tab=tab)


@tabs_bp.route('/<int:tab_id>/delete', methods=['POST'])
@login_required
def delete_tab(tab_id):
    tab = Tab.query.get_or_404(tab_id)
    db.session.delete(tab)
    db.session.commit()
    return redirect(url_for('tabs.index'))
