from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from datetime import datetime
from app import db
from app.models.main import Admin

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        user = Admin.query.filter_by(username=username).first()

        if not user or not check_password_hash(user.password, password):
            flash('اسم المستخدم أو كلمة المرور غير صحيحة.', 'danger')
            return redirect(url_for('auth.login'))

        if not user.is_active:
            flash('حسابك موقوف. تواصل مع المدير.', 'danger')
            return redirect(url_for('auth.login'))

        login_user(user, remember=remember)
        user.last_login = datetime.utcnow()
        db.session.commit()

        next_page = request.args.get('next')
        if not next_page:
            pos_only = (user.role not in ('superadmin', 'admin')
                        and user.has_perm('perm_pos')
                        and not any(user.has_perm(p) for p in [
                            'perm_bookings', 'perm_courts', 'perm_products',
                            'perm_orders', 'perm_expenses', 'perm_reports',
                            'perm_users', 'perm_settings']))
            next_page = url_for('pos.quick_sale') if pos_only else url_for('admin.bookings')
        return redirect(next_page)

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('تم تسجيل الخروج بنجاح.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/forgot-password')
def forgot_password():
    flash('يرجى التواصل مع مدير النظام لإعادة تعيين كلمة المرور.', 'info')
    return redirect(url_for('auth.login'))