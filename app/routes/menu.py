import os
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from flask_login import login_required, current_user

from app import db
from app.models.store import Category, Product

menu_bp = Blueprint('menu', __name__)

# The café menu is published on its own subdomain; everything else lives on the main site.
MENU_HOST = os.environ.get('MENU_HOST', 'menu.z-padel.com').lower()
MAIN_URL  = os.environ.get('MAIN_URL', 'https://z-padel.com').rstrip('/')


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


# ═══════════════════════════════════════════
# PUBLIC  (menu.z-padel.com/, and /menu/ on the main site as a preview)
# ═══════════════════════════════════════════
@menu_bp.route('/menu/')
def public_menu():
    resp = render_template('menu/public.html', sections=menu_sections(g.lang),
                           main_url=MAIN_URL if is_menu_host() else '')
    return resp, 200, {'Cache-Control': 'no-cache'}


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
                           menu_url=f'https://{MENU_HOST}')
