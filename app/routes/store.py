from flask import Blueprint, render_template, redirect, url_for, request, flash, session, jsonify
from app.models.store import Product, Category, Order, OrderItem
from app import db

store_bp = Blueprint('store', __name__)


@store_bp.route('/')
def shop():
    cats   = Category.query.all()
    cat_id = request.args.get('cat')
    prods  = Product.query.filter_by(is_active=True, show_on_website=True)
    if cat_id:
        prods = prods.filter_by(category_id=cat_id)
    cart       = session.get('cart', {})
    cart_count = sum(cart.values())
    return render_template('store/shop.html',
                           products=prods.all(),
                           categories=cats,
                           cart_count=cart_count)


@store_bp.route('/cart/add/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    p = Product.query.get_or_404(product_id)
    if p.stock == 0:
        return jsonify(success=False, message='نفذ المخزون')
    cart      = session.get('cart', {})
    key       = str(product_id)
    cart[key] = cart.get(key, 0) + 1
    session['cart']  = cart
    session.modified = True
    return jsonify(success=True, qty=cart[key], cart_count=sum(cart.values()))


@store_bp.route('/cart/remove/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):
    cart = session.get('cart', {})
    key  = str(product_id)
    if key in cart:
        cart[key] -= 1
        if cart[key] <= 0:
            del cart[key]
    session['cart']  = cart
    session.modified = True
    return jsonify(success=True, cart_count=sum(cart.values()))


@store_bp.route('/cart/clear', methods=['POST'])
def clear_cart():
    session.pop('cart', None)
    return redirect(url_for('store.cart'))


@store_bp.route('/cart')
def cart():
    cart  = session.get('cart', {})
    items = []
    total = 0
    for pid, qty in cart.items():
        p = Product.query.get(int(pid))
        if p:
            subtotal = p.price * qty
            total   += subtotal
            items.append({'product': p, 'qty': qty, 'subtotal': subtotal})
    return render_template('store/cart.html',
                           items=items,
                           total=total,
                           cart_count=sum(cart.values()))


@store_bp.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart  = session.get('cart', {})
    items = []
    total = 0
    for pid, qty in cart.items():
        p = Product.query.get(int(pid))
        if p:
            subtotal = p.price * qty
            total   += subtotal
            items.append({'product': p, 'qty': qty, 'subtotal': subtotal})

    if request.method == 'POST':
        if not items:
            flash('السلة فارغة!', 'danger')
            return redirect(url_for('store.shop'))
        try:
            order = Order(
                customer_name=request.form.get('customer_name', ''),
                customer_phone=request.form.get('customer_phone', ''),
                total_price=total,
                status='pending',
                notes=request.form.get('notes', ''),
            )
            db.session.add(order)
            db.session.flush()
            for item in items:
                oi = OrderItem(
                    order_id=order.id,
                    product_id=item['product'].id,
                    quantity=item['qty'],
                    price=item['product'].price,
                    subtotal=item['subtotal'],
                )
                db.session.add(oi)
            db.session.commit()
            session.pop('cart', None)
            flash('تم استلام طلبك بنجاح! سيتم التواصل معك قريباً.', 'success')
            return redirect(url_for('store.shop'))
        except Exception as e:
            db.session.rollback()
            flash(f'حدث خطأ: {e}', 'danger')

    return render_template('store/checkout.html',
                           items=items,
                           total=total,
                           cart_count=sum(cart.values()))