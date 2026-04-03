from flask import Blueprint, render_template, redirect, url_for, request, flash
from app.models.store import Product, Category, Order, OrderItem

store_bp = Blueprint('store', __name__)


@store_bp.route('/')
def shop():
    cats   = Category.query.all()
    cat_id = request.args.get('cat')
    prods  = Product.query.filter_by(is_active=True)
    if cat_id:
        prods = prods.filter_by(category_id=cat_id)
    return render_template('store/shop.html', products=prods.all(), categories=cats)


@store_bp.route('/cart')
def cart():
    return render_template('store/cart.html')


@store_bp.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if request.method == 'POST':
        flash('تم استلام طلبك بنجاح!', 'success')
        return redirect(url_for('store.shop'))
    return render_template('store/checkout.html')