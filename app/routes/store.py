from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from app.models.store import Product, Order, OrderItem
from app import db

store = Blueprint('store', __name__, url_prefix='/store')


# ── helpers ───────────────────────────────────────────────
def get_cart():
    return session.get('cart', {})

def save_cart(cart):
    session['cart'] = cart
    session.modified = True

def cart_total(cart):
    total = 0
    for pid, qty in cart.items():
        p = Product.query.get(int(pid))
        if p:
            total += p.price * qty
    return total


# ── Shop page  (website only — show_on_website=True) ──────
@store.route('/')
def shop():
    products   = Product.query.filter_by(is_active=True, show_on_website=True).order_by(Product.id.desc()).all()
    cart       = get_cart()
    cart_count = sum(cart.values())
    return render_template('store/shop.html', products=products, cart_count=cart_count)


# ── Cart count API (used by homepage pill) ────────────────
@store.route('/cart/count')
def cart_count_api():
    return jsonify({'count': sum(get_cart().values())})


# ── Cart page ─────────────────────────────────────────────
@store.route('/cart')
def cart():
    cart  = get_cart()
    items = []
    for pid, qty in cart.items():
        p = Product.query.get(int(pid))
        if p:
            items.append({'product': p, 'qty': qty, 'subtotal': p.price * qty})
    total = sum(i['subtotal'] for i in items)
    return render_template('store/cart.html', items=items, total=total)


# ── Add to cart (AJAX) ────────────────────────────────────
@store.route('/cart/add/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    cart    = get_cart()
    pid     = str(product_id)
    qty     = cart.get(pid, 0) + 1
    if product.stock > 0 and qty > product.stock:
        return jsonify({'success': False, 'message': 'Out of stock'})
    cart[pid] = qty
    save_cart(cart)
    return jsonify({'success': True, 'cart_count': sum(cart.values()), 'qty': qty})


# ── Update qty (AJAX) ─────────────────────────────────────
@store.route('/cart/update/<int:product_id>', methods=['POST'])
def update_cart(product_id):
    data = request.get_json(silent=True) or {}
    qty  = int(data.get('qty', 0))
    cart = get_cart()
    pid  = str(product_id)
    cart.pop(pid, None) if qty <= 0 else cart.update({pid: qty})
    save_cart(cart)
    p        = Product.query.get(product_id)
    subtotal = (p.price * qty) if p and qty > 0 else 0
    return jsonify({'success': True, 'cart_count': sum(cart.values()),
                    'total': cart_total(cart), 'subtotal': subtotal})


# ── Remove from cart (AJAX) ───────────────────────────────
@store.route('/cart/remove/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):
    cart = get_cart()
    cart.pop(str(product_id), None)
    save_cart(cart)
    return jsonify({'success': True, 'cart_count': sum(cart.values()), 'total': cart_total(cart)})


# ── Checkout ──────────────────────────────────────────────
@store.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart = get_cart()
    if not cart:
        flash('سلة التسوق فارغة')
        return redirect(url_for('store.shop'))

    items = []
    for pid, qty in cart.items():
        p = Product.query.get(int(pid))
        if p:
            items.append({'product': p, 'qty': qty, 'subtotal': p.price * qty})
    total = sum(i['subtotal'] for i in items)

    if request.method == 'POST':
        name  = request.form.get('customer_name', '').strip()
        phone = request.form.get('customer_phone', '').strip()
        notes = request.form.get('notes', '').strip()
        if not name or not phone:
            flash('الرجاء إدخال الاسم والهاتف')
            return render_template('store/checkout.html', items=items, total=total)
        order = Order(customer_name=name, customer_phone=phone,
                      notes=notes, total_price=total, status='pending', source='website')
        db.session.add(order)
        db.session.flush()
        for item in items:
            db.session.add(OrderItem(order_id=order.id, product_id=item['product'].id,
                                     quantity=item['qty'], unit_price=item['product'].price))
        db.session.commit()
        save_cart({})
        return redirect(url_for('store.order_success', order_id=order.id))

    return render_template('store/checkout.html', items=items, total=total)


# ── Order success ─────────────────────────────────────────
@store.route('/order/<int:order_id>/success')
def order_success(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template('store/success.html', order=order)