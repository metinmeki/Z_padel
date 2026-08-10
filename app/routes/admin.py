import os, uuid, subprocess
from datetime import datetime, date, timedelta, time as dtime

def _parse_time(t):
    if t == '24:00':
        return dtime(23, 59)
    return datetime.strptime(t, '%H:%M').time()
from flask import (Blueprint, render_template, redirect, url_for,
                   request, flash, current_app, send_file, jsonify)
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import func
from app import db
from app.models.main  import (Admin, Court, Booking, CancelRequest,
                               Coach, TrainingRequest, SystemSetting, GameClip,
                               ActivityTable, ActivitySession, ActivitySessionItem, ACTIVITY_META,
                               Sponsor)
from app.models.store import (Category, Product, Order, OrderItem,
                               Expense, ExpenseCategory)
from sqlalchemy import func, case
admin_bp = Blueprint('admin', __name__)

FINANCE_USERS = {'yaser', 'mazin'}

# ── helpers ──
def allowed_file(filename):
    return ('.' in filename and
            filename.rsplit('.', 1)[1].lower()
            in current_app.config['ALLOWED_EXTENSIONS'])

def _dark_bg_to_transparent(img):
    """Convert edge-connected dark background to transparent (RGBA output).
    Used for sponsor logos so they display cleanly on any background."""
    from collections import deque
    from PIL import Image as _Image
    rgb = img.convert('RGB')
    w, h = rgb.size
    px = rgb.load()
    corners = [px[0,0], px[w-1,0], px[0,h-1], px[w-1,h-1]]
    if sum(r+g+b for r,g,b in corners) / (len(corners)*3) > 80:
        return img.convert('RGBA')
    rgba = img.convert('RGBA')
    data = rgba.load()
    visited = [[False]*h for _ in range(w)]
    queue = deque()
    def is_dark(x, y):
        r, g, b = data[x, y][:3]
        return r < 60 and g < 60 and b < 60
    for x in range(w):
        for y in (0, h-1):
            if not visited[x][y] and is_dark(x, y):
                visited[x][y] = True
                queue.append((x, y))
    for y in range(h):
        for x in (0, w-1):
            if not visited[x][y] and is_dark(x, y):
                visited[x][y] = True
                queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        r, g, b, _ = data[x, y]
        data[x, y] = (r, g, b, 0)
        for dx, dy in ((-1,0),(1,0),(0,-1),(0,1)):
            nx, ny = x+dx, y+dy
            if 0 <= nx < w and 0 <= ny < h and not visited[nx][ny] and is_dark(nx, ny):
                visited[nx][ny] = True
                queue.append((nx, ny))
    return rgba


def _remove_dark_bg(img):
    """Replace dark background with white using edge-connected flood fill.
    Only pixels reachable from image edges with R,G,B < 60 are replaced."""
    from collections import deque
    from PIL import Image as _Image
    rgb = img.convert('RGB')
    w, h = rgb.size
    px = rgb.load()
    # Sample corners — if not dark, skip processing
    corners = [px[0,0], px[w-1,0], px[0,h-1], px[w-1,h-1]]
    if sum(r+g+b for r,g,b in corners) / (len(corners)*3) > 80:
        return img
    rgba = img.convert('RGBA')
    data = rgba.load()
    visited = [[False]*h for _ in range(w)]
    queue = deque()
    def is_dark(x, y):
        r, g, b = data[x, y][:3]
        return r < 60 and g < 60 and b < 60
    for x in range(w):
        for y in (0, h-1):
            if not visited[x][y] and is_dark(x, y):
                visited[x][y] = True
                queue.append((x, y))
    for y in range(h):
        for x in (0, w-1):
            if not visited[x][y] and is_dark(x, y):
                visited[x][y] = True
                queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        data[x, y] = (255, 255, 255, 255)
        for dx, dy in ((-1,0),(1,0),(0,-1),(0,1)):
            nx, ny = x+dx, y+dy
            if 0 <= nx < w and 0 <= ny < h and not visited[nx][ny] and is_dark(nx, ny):
                visited[nx][ny] = True
                queue.append((nx, ny))
    result = _Image.new('RGB', rgba.size, (255, 255, 255))
    result.paste(rgba, mask=rgba.split()[3])
    return result


def save_upload(file, folder_key='UPLOAD_FOLDER', fix_bg=True):
    if not file or file.filename == '':
        return None
    ext = file.filename.rsplit('.', 1)[1].lower()
    if ext not in ['jpg', 'jpeg', 'png', 'webp', 'gif']:
        return None

    upload_dir = os.path.join(current_app.static_folder, 'images', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)

    # Save as WebP for all non-gif uploads (50-80% smaller)
    from PIL import Image
    import io

    try:
        img = Image.open(file.stream)

        if fix_bg:
            # Convert palette/RGBA to RGB for WebP compatibility
            if img.mode in ('RGBA', 'LA'):
                bg = Image.new('RGB', img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[-1])
                img = bg
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            img.thumbnail((900, 900), Image.LANCZOS)
            img = _remove_dark_bg(img)
        else:
            # Logo mode: preserve or convert transparency
            if img.mode == 'P':
                img = img.convert('RGBA')
            elif img.mode == 'LA':
                img = img.convert('RGBA')
            elif img.mode == 'RGB':
                img = _dark_bg_to_transparent(img)
            # RGBA: kept as-is
            img.thumbnail((900, 900), Image.LANCZOS)

        out_name = f"{uuid.uuid4().hex}.webp"
        img.save(
            os.path.join(upload_dir, out_name),
            format='WEBP',
            quality=82,
            method=4,    # compression effort (0=fast, 6=best)
        )
        return out_name

    except Exception:
        # Fallback: save original if Pillow fails
        name = f"{uuid.uuid4().hex}.{ext}"
        file.seek(0)
        file.save(os.path.join(upload_dir, name))
        return name

def save_b64_image(b64_data):
    """Decode a browser-compressed base64 image and save as WebP."""
    if not b64_data:
        return None
    import base64, io
    from PIL import Image
    try:
        # strip data:image/jpeg;base64, prefix
        header, data = b64_data.split(',', 1)
        raw = base64.b64decode(data)
        img = Image.open(io.BytesIO(raw))
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img = _remove_dark_bg(img)
        upload_dir = os.path.join(current_app.static_folder, 'images', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        out_name = f"{uuid.uuid4().hex}.webp"
        img.save(os.path.join(upload_dir, out_name), format='WEBP', quality=82, method=4)
        return out_name
    except Exception:
        return None

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_active:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


# ════════════════════════════════════════════
# DASHBOARD
# ════════════════════════════════════════════
@admin_bp.route('/fix-image-backgrounds')
@login_required
def fix_image_backgrounds():
    if current_user.role not in ('superadmin', 'admin'):
        flash('Access denied.', 'danger')
        return redirect(url_for('admin.dashboard'))
    from PIL import Image as _PIL_Image
    import glob as _glob
    upload_dir = os.path.join(current_app.static_folder, 'images', 'uploads')
    files = _glob.glob(os.path.join(upload_dir, '*.webp')) + \
            _glob.glob(os.path.join(upload_dir, '*.jpg')) + \
            _glob.glob(os.path.join(upload_dir, '*.jpeg')) + \
            _glob.glob(os.path.join(upload_dir, '*.png'))
    fixed = 0
    skipped = 0
    for path in files:
        try:
            img = _PIL_Image.open(path)
            result = _remove_dark_bg(img)
            if result is not img:
                result.save(path, format='WEBP', quality=82, method=4)
                fixed += 1
            else:
                skipped += 1
        except Exception:
            skipped += 1
    flash(f'Done: {fixed} images fixed, {skipped} skipped (no dark background).', 'success')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/')
@admin_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.username.lower() not in FINANCE_USERS:
        flash('Access denied.', 'danger')
        return redirect(url_for('admin.bookings'))
    today = date.today()
    now_h = datetime.now().hour

    total_bookings   = Booking.query.count()
    today_bookings   = Booking.query.filter_by(booking_date=today).count()
    pending_count    = Booking.query.filter_by(status='pending').count()
    confirmed_count  = Booking.query.filter_by(status='confirmed').count()
    cancelled_count  = Booking.query.filter_by(status='cancelled').count()
    total_orders     = Order.query.count()

    today_revenue = (db.session.query(func.sum(Booking.total_price))
                     .filter(Booking.booking_date == today,
                             Booking.status == 'confirmed').scalar() or 0)

    month_start   = today.replace(day=1)
    month_revenue = (db.session.query(func.sum(Booking.total_price))
                     .filter(Booking.booking_date >= month_start,
                             Booking.status == 'confirmed').scalar() or 0)

    week_start    = today - timedelta(days=6)
    week_revenue  = (db.session.query(func.sum(Booking.total_price))
                     .filter(Booking.booking_date >= week_start,
                             Booking.status == 'confirmed').scalar() or 0)

    store_revenue = (db.session.query(func.sum(Order.total_price))
                     .filter_by(status='completed').scalar() or 0)

    courts          = Court.query.filter_by(is_active=True).all()
    recent_bookings = (Booking.query.order_by(Booking.created_at.desc())
                       .limit(8).all())

    # Chart data — last 7 days
    week_labels, week_data, week_revenue_data = [], [], []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        week_labels.append(d.strftime('%a'))
        cnt = Booking.query.filter_by(booking_date=d, status='confirmed').count()
        rev = (db.session.query(func.sum(Booking.total_price))
               .filter_by(booking_date=d, status='confirmed').scalar() or 0)
        week_data.append(cnt)
        week_revenue_data.append(int(rev))

    return render_template('admin/dashboard.html',
        total_bookings=total_bookings, today_bookings=today_bookings,
        pending_count=pending_count, confirmed_count=confirmed_count,
        cancelled_count=cancelled_count, total_orders=total_orders,
        today_revenue=today_revenue, month_revenue=month_revenue,
        week_revenue=week_revenue, store_revenue=store_revenue,
        courts=courts, recent_bookings=recent_bookings,
        current_hour=now_h,
        week_labels=week_labels, week_data=week_data,
        week_revenue_data=week_revenue_data,
    )


# ════════════════════════════════════════════
# BOOKINGS
# ════════════════════════════════════════════
@admin_bp.route('/bookings', methods=['GET', 'POST'])
@login_required
def bookings():
    if request.method == 'POST':
        return redirect(url_for('admin.bookings'))
    q = Booking.query
    if request.args.get('date'):
        q = q.filter_by(booking_date=datetime.strptime(request.args['date'], '%Y-%m-%d').date())
    if request.args.get('court_id'):
        q = q.filter_by(court_id=request.args['court_id'])
    if request.args.get('status'):
        q = q.filter_by(status=request.args['status'])

    courts     = Court.query.filter_by(is_active=True).all()
    today_date = date.today()

    def _bk_sort_key(b):
        d = b.booking_date or date.min
        t = (b.start_time.hour * 60 + b.start_time.minute) if b.start_time else 0
        if d == today_date:
            return (0, 0, t)          # Today: priority 0, sorted by time
        elif d > today_date:
            return (1, (d - today_date).days, t)   # Future: soonest first
        else:
            return (2, (today_date - d).days, t)   # Past: most recent first

    all_bk = sorted(q.limit(500).all(), key=_bk_sort_key)

    from datetime import timedelta
    tomorrow = (today_date + timedelta(days=1)).isoformat()

    return render_template('admin/bookings.html',
        bookings=all_bk, pagination=None,
        courts=courts, today=today_date.isoformat(),
        tomorrow=tomorrow, court_price=25000)


@admin_bp.route('/bookings/booked-slots')
@login_required
def booked_slots():
    """Return booked time ranges for a court+date so the frontend can disable them."""
    court_id = request.args.get('court_id', type=int)
    date_str  = request.args.get('date', '')
    if not court_id or not date_str:
        return jsonify(booked=[])
    try:
        bk_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify(booked=[])
    bks = Booking.query.filter(
        Booking.court_id == court_id,
        Booking.booking_date == bk_date,
        Booking.status.in_(['confirmed', 'pending'])
    ).all()
    booked = []
    for b in bks:
        if b.start_time and b.end_time:
            booked.append({
                'start': b.start_time.strftime('%H:%M'),
                'end':   b.end_time.strftime('%H:%M'),
                'name':  b.customer_name
            })
    return jsonify(booked=booked)


@admin_bp.route('/bookings/add', methods=['POST'])
@login_required
def add_booking():
    try:
        court  = Court.query.get_or_404(request.form['court_id'])
        b_date = datetime.strptime(request.form['booking_date'], '%Y-%m-%d').date()
        s_time = _parse_time(request.form['start_time'])
        e_time = _parse_time(request.form['end_time'])

        bk = Booking(
            court_id=court.id,
            customer_name=request.form['customer_name'],
            customer_phone=request.form['customer_phone'],
            booking_date=b_date,
            start_time=s_time,
            end_time=e_time,
            status=request.form.get('status', 'confirmed'),
            notes=request.form.get('notes', ''),
        )
        bk.total_price = bk.calc_price(court.price_per_hour)
        db.session.add(bk)
        db.session.commit()
        flash('تم إضافة الحجز بنجاح.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ: {e}', 'danger')
    return redirect(url_for('admin.bookings'))


@admin_bp.route('/bookings/<int:booking_id>')
@login_required
def booking_detail(booking_id):
    b = Booking.query.get_or_404(booking_id)
    return render_template('admin/booking_detail.html', booking=b)


@admin_bp.route('/bookings/<int:booking_id>/edit', methods=['POST'])
@login_required
def edit_booking(booking_id):
    b = Booking.query.get_or_404(booking_id)
    try:
        b.customer_name  = request.form.get('customer_name', b.customer_name)
        b.customer_phone = request.form.get('customer_phone', b.customer_phone)
        b.status         = request.form.get('status', b.status)
        b.notes          = request.form.get('notes', b.notes)
        s_str = request.form.get('start_time', '')
        e_str = request.form.get('end_time', '')
        if s_str and e_str:
            b.start_time = _parse_time(s_str)
            b.end_time   = _parse_time(e_str)
            court = b.court
            if court:
                b.total_price = b.calc_price(court.price_per_hour)
        db.session.commit()
        flash('تم تحديث الحجز.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'خطأ: {e}', 'danger')
    return redirect(url_for('admin.bookings'))


def _find_midnight_continuation(b):
    """If booking ends at 23:59, find its next-day continuation (cross-midnight split)."""
    from datetime import timedelta, time as dtime
    if b.end_time and b.end_time.hour == 23 and b.end_time.minute == 59:
        tomorrow = b.booking_date + timedelta(days=1)
        return Booking.query.filter_by(
            court_id=b.court_id,
            booking_date=tomorrow,
            start_time=dtime(0, 0),
            customer_phone=b.customer_phone,
        ).filter(Booking.status != 'cancelled').first()
    return None


@admin_bp.route('/bookings/<int:booking_id>/confirm', methods=['GET', 'POST'])
@login_required
def confirm_booking(booking_id):
    b = Booking.query.get_or_404(booking_id)
    b.status = 'confirmed'
    linked = _find_midnight_continuation(b)
    if linked:
        linked.status = 'confirmed'
    db.session.commit()
    flash('تم تأكيد الحجز.', 'success')
    return redirect(url_for('admin.pending_bookings'))


@admin_bp.route('/bookings/<int:booking_id>/reject', methods=['GET', 'POST'])
@login_required
def reject_booking(booking_id):
    b = Booking.query.get_or_404(booking_id)
    b.status = 'cancelled'
    linked = _find_midnight_continuation(b)
    if linked:
        linked.status = 'cancelled'
    db.session.commit()
    flash('تم رفض الحجز.', 'success')
    return redirect(url_for('admin.pending_bookings'))


@admin_bp.route('/bookings/<int:booking_id>/cancel', methods=['POST'])
@login_required
def cancel_booking(booking_id):
    b = Booking.query.get_or_404(booking_id)
    b.status = 'cancelled'
    db.session.commit()
    flash('تم إلغاء الحجز.', 'success')
    return redirect(url_for('admin.bookings'))


@admin_bp.route('/bookings/confirm-all-pending')
@login_required
def confirm_all_pending():
    Booking.query.filter_by(status='pending').update({'status': 'confirmed'})
    db.session.commit()
    flash('تم تأكيد جميع الحجوزات المعلقة.', 'success')
    return redirect(url_for('admin.pending_bookings'))


@admin_bp.route('/pending-bookings')
@login_required
def pending_bookings():
    from datetime import timedelta, time as dtime
    pending = Booking.query.filter_by(status='pending').order_by(Booking.created_at.asc()).all()
    courts  = Court.query.filter_by(is_active=True).all()
    today   = date.today()
    now     = datetime.utcnow()

    # Group cross-midnight split bookings: hide continuation, augment parent
    continuation_ids = set()
    linked_map = {}  # parent booking id → continuation booking
    for b in pending:
        if b.end_time and b.end_time.hour == 23 and b.end_time.minute == 59:
            tomorrow = b.booking_date + timedelta(days=1)
            cont = next((
                x for x in pending
                if x.court_id == b.court_id
                and x.booking_date == tomorrow
                and x.start_time and x.start_time.hour == 0 and x.start_time.minute == 0
                and x.customer_phone == b.customer_phone
            ), None)
            if cont:
                continuation_ids.add(cont.id)
                linked_map[b.id] = cont

    display = [b for b in pending if b.id not in continuation_ids]

    urgent  = sum(1 for b in display if (now - b.created_at).total_seconds() > 7200)
    today_p = sum(1 for b in display if b.booking_date == today)

    today_start = datetime(today.year, today.month, today.day, 0, 0, 0)
    conf_t = Booking.query.filter(
        Booking.status == 'confirmed',
        Booking.updated_at >= today_start
    ).count()

    return render_template('admin/pending_bookings.html',
        pending_bookings=display, linked_map=linked_map, courts=courts,
        urgent_count=urgent, today_pending=today_p, confirmed_today=conf_t)

# ════════════════════════════════════════════
# CANCEL REQUESTS
# ════════════════════════════════════════════
@admin_bp.route('/cancel-requests')
@login_required
def cancel_requests():
    reqs = CancelRequest.query.order_by(CancelRequest.created_at.desc()).all()
    approved_count = CancelRequest.query.filter_by(status='approved').count()
    rejected_count = CancelRequest.query.filter_by(status='rejected').count()
    return render_template('admin/cancel_requests.html',
        cancel_requests=reqs,
        approved_count=approved_count,
        rejected_count=rejected_count)


@admin_bp.route('/cancel-requests/<int:req_id>/approve', methods=['POST'])
@login_required
def approve_cancel(req_id):
    cr = CancelRequest.query.get_or_404(req_id)
    cr.status = 'approved'
    cr.booking.status = 'cancelled'
    db.session.commit()
    flash('تم قبول طلب الإلغاء.', 'success')
    return redirect(url_for('admin.cancel_requests'))


@admin_bp.route('/cancel-requests/<int:req_id>/reject', methods=['POST'])
@login_required
def reject_cancel(req_id):
    cr = CancelRequest.query.get_or_404(req_id)
    cr.status = 'rejected'
    db.session.commit()
    flash('تم رفض طلب الإلغاء.', 'success')
    return redirect(url_for('admin.cancel_requests'))


# ════════════════════════════════════════════
# COURTS
# ════════════════════════════════════════════
@admin_bp.route('/courts')
@login_required
def courts():
    all_courts = Court.query.all()
    return render_template('admin/courts.html', courts=all_courts)


@admin_bp.route('/courts/add', methods=['POST'])
@login_required
def add_court():
    court = Court(
        name=request.form['name'],
        price_per_hour=float(request.form.get('price_per_hour', 25000)),
        color=request.form.get('color', '#1565C0'),
        description=request.form.get('description', ''),
        capacity=request.form.get('capacity') or None,
        surface_type=request.form.get('surface_type', ''),
    )
    db.session.add(court)
    db.session.commit()
    flash('تم إضافة الملعب بنجاح.', 'success')
    return redirect(url_for('admin.courts'))


@admin_bp.route('/courts/<int:court_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_court(court_id):
    court = Court.query.get_or_404(court_id)
    if request.method == 'POST':
        court.name           = request.form.get('name', court.name)
        court.price_per_hour = float(request.form.get('price_per_hour', court.price_per_hour or 25000))
        court.color          = request.form.get('color', court.color)
        court.description    = request.form.get('description', court.description)
        court.capacity       = request.form.get('capacity') or None
        court.surface_type   = request.form.get('surface_type', court.surface_type)
        court.is_active      = request.form.get('is_active', '1') == '1'
        if request.form.get('remove_image'):
            court.image = None
        new_img = save_upload(request.files.get('image'))
        if new_img:
            court.image = new_img
        db.session.commit()
        flash('تم تحديث الملعب بنجاح.', 'success')
        return redirect(url_for('admin.courts'))
    return render_template('admin/edit_court.html', court=court)


@admin_bp.route('/courts/<int:court_id>/toggle', methods=['POST'])
@login_required
def toggle_court(court_id):
    c = Court.query.get_or_404(court_id)
    c.is_active = not c.is_active
    db.session.commit()
    return redirect(url_for('admin.courts'))


@admin_bp.route('/courts/<int:court_id>/delete', methods=['POST'])
@login_required
def delete_court(court_id):
    c = Court.query.get_or_404(court_id)
    db.session.delete(c)
    db.session.commit()
    flash('تم حذف الملعب.', 'success')
    return redirect(url_for('admin.courts'))


# ════════════════════════════════════════════
# PRODUCTS
# ════════════════════════════════════════════
@admin_bp.route('/products')
@login_required
def products():
    prods = Product.query.order_by(Product.created_at.desc()).all()
    cats  = Category.query.all()
    return render_template('admin/products.html', products=prods, categories=cats)


@admin_bp.route('/products/new', methods=['GET', 'POST'])
@login_required
def new_product():
    cats = Category.query.all()
    if request.method == 'POST':
        img = save_b64_image(request.form.get('image_b64'))
        p = Product(
            name=request.form.get('name', ''),
            category_id=request.form.get('category_id') or None,
            price=float(request.form.get('price') or 0),
            stock=int(request.form.get('stock') or 0),
            description=request.form.get('description', ''),
            description_ar=request.form.get('description_ar', ''),
            description_ku=request.form.get('description_ku', ''),
            barcode=request.form.get('barcode') or None,
            show_on_website=request.form.get('show_on_website') == '1',
            is_active='is_active' in request.form,
            image=img,
        )
        db.session.add(p)
        db.session.commit()
        flash('تم إضافة المنتج بنجاح.', 'success')
        return redirect(url_for('admin.products'))
    return render_template('admin/product_form.html', product=None, categories=cats)


@admin_bp.route('/products/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    p    = Product.query.get_or_404(product_id)
    cats = Category.query.all()
    if request.method == 'POST':
        p.name            = request.form.get('name', p.name)
        p.price           = float(request.form.get('price') or p.price)
        p.stock           = int(request.form.get('stock') or p.stock)
        p.description     = request.form.get('description', p.description)
        p.description_ar  = request.form.get('description_ar', p.description_ar)
        p.description_ku  = request.form.get('description_ku', p.description_ku)
        p.barcode         = request.form.get('barcode') or p.barcode
        p.category_id     = request.form.get('category_id') or p.category_id
        p.show_on_website = request.form.get('show_on_website') == '1'
        p.is_active       = 'is_active' in request.form
        new_img = save_b64_image(request.form.get('image_b64'))
        if new_img:
            p.image = new_img
        db.session.commit()
        flash('تم تحديث المنتج.', 'success')
        return redirect(url_for('admin.products'))
    return render_template('admin/product_form.html', product=p, categories=cats)

@admin_bp.route('/products/<int:product_id>/delete', methods=['POST'])
@login_required
def delete_product(product_id):
    p = Product.query.get_or_404(product_id)
    db.session.delete(p)
    db.session.commit()
    flash('تم حذف المنتج.', 'success')
    return redirect(url_for('admin.products'))


# ════════════════════════════════════════════
# CATEGORIES
# ════════════════════════════════════════════
@admin_bp.route('/categories')
@login_required
def categories():
    cats = Category.query.all()
    return render_template('admin/categories.html', categories=cats)


@admin_bp.route('/categories/add', methods=['POST'])
@login_required
def add_category():
    from sqlalchemy.exc import IntegrityError
    name = request.form.get('name', '').strip()
    if not name:
        flash('اسم الفئة مطلوب. / Category name is required.', 'danger')
        return redirect(url_for('admin.categories'))
    cat = Category(name=name, color=request.form.get('color', '#1565C0'),
                   show_in_store=request.form.get('show_in_store') == '1')
    db.session.add(cat)
    try:
        db.session.commit()
        flash('تم إضافة الفئة.', 'success')
    except IntegrityError:
        db.session.rollback()
        flash(f'فئة باسم "{name}" موجودة مسبقاً. / A category named "{name}" already exists.', 'danger')
    return redirect(url_for('admin.categories'))


@admin_bp.route('/categories/<int:cat_id>/delete', methods=['POST'])
@login_required
def delete_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    db.session.delete(cat)
    db.session.commit()
    flash('تم حذف الفئة.', 'success')
    return redirect(url_for('admin.categories'))


# ════════════════════════════════════════════
# ORDERS
# ════════════════════════════════════════════
from flask import jsonify, request

from flask import jsonify, request, render_template
from sqlalchemy.orm import joinedload  # Ensure this is imported


@admin_bp.route('/orders')
@login_required
def orders():
    # .options(joinedload(Order.items)) loads everything in 1 query, not 20+ queries
    q = Order.query.options(joinedload(Order.items))

    if request.args.get('status'):
        q = q.filter_by(status=request.args['status'])
    if request.args.get('date'):
        d = datetime.strptime(request.args['date'], '%Y-%m-%d').date()
        q = q.filter(func.date(Order.created_at) == d)

    page = request.args.get('page', 1, type=int)
    pag = q.order_by(Order.created_at.desc()).paginate(page=page, per_page=20)

    return render_template('admin/orders.html', orders=pag.items, pagination=pag)


@admin_bp.route('/orders/<int:order_id>/status', methods=['POST'])
@login_required
def update_order_status(order_id):
    o = Order.query.get_or_404(order_id)
    # Get status from the form
    o.status = request.form.get('status')
    db.session.commit()
    return jsonify({"success": True, "new_status": o.status})


@admin_bp.route('/orders/<int:order_id>/delete', methods=['POST'])
@login_required
def delete_order(order_id):
    o = Order.query.get_or_404(order_id)
    db.session.delete(o)
    db.session.commit()
    return jsonify({"success": True})
# ════════════════════════════════════════════
# EXPENSES
# ════════════════════════════════════════════
@admin_bp.route('/expenses')
@login_required
def expenses():
    from sqlalchemy import func
    from calendar import monthrange

    q = Expense.query
    if request.args.get('month'):
        y, m = map(int, request.args['month'].split('-'))
        last_day = monthrange(y, m)[1]
        q = q.filter(Expense.date >= date(y, m, 1),
                     Expense.date <= date(y, m, last_day))

    page = request.args.get('page', 1, type=int)
    pag = q.order_by(Expense.date.desc()).paginate(page=page, per_page=20)

    today = date.today()
    month_start = today.replace(day=1)

    cats = db.session.query(
        ExpenseCategory,
        func.sum(Expense.amount).label('total')
    ).outerjoin(Expense).group_by(ExpenseCategory.id).all()

    cats_with_totals = [
        {'id': c[0].id, 'name': c[0].name, 'color': c[0].color, 'total': c[1] or 0}
        for c in cats
    ]

    totals = db.session.query(
        func.sum(Expense.amount).label('total'),
        func.sum(case((Expense.date == today, Expense.amount), else_=0)).label('today'),
        func.sum(case((Expense.date >= month_start, Expense.amount), else_=0)).label('month')
    ).first()

    total_exp = totals.total or 0
    today_exp = totals.today or 0
    month_exp = totals.month or 0

    total_rev = (db.session.query(func.sum(Booking.total_price))
                 .filter_by(status='confirmed').scalar() or 0)

    monthly_trend = []
    for i in range(5, -1, -1):
        d = today.replace(day=1) - timedelta(days=i * 28)
        d = d.replace(day=1)
        nm = d.replace(day=28) + timedelta(days=4)
        nm = nm.replace(day=1)
        total = (db.session.query(func.sum(Expense.amount))
                 .filter(Expense.date >= d, Expense.date < nm).scalar() or 0)
        monthly_trend.append({'label': d.strftime('%b'), 'total': total})

    budget = float(SystemSetting.get('monthly_budget', 1_000_000))

    return render_template('admin/expenses.html',
                           expenses=pag.items, pagination=pag,
                           expense_categories=cats_with_totals,
                           total_expenses=total_exp, today_expenses=today_exp,
                           month_expenses=month_exp, total_revenue=total_rev,
                           monthly_trend=monthly_trend, monthly_budget=budget,
                           today=today.isoformat(),
                           )


@admin_bp.route('/expenses/add', methods=['POST'])
@login_required
def add_expense():
    try:
        # ✅ receipt is optional — only save if a file was actually uploaded
        receipt = None
        file = request.files.get('receipt')
        if file and file.filename:
            receipt = save_upload(file, 'RECEIPTS_FOLDER')

        e = Expense(
            description=request.form['description'],
            amount=float(request.form['amount']),
            date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
            category_id=request.form.get('category_id') or None,
            notes=request.form.get('notes', ''),
            receipt=receipt,
            added_by=current_user.username,
        )
        db.session.add(e)
        db.session.commit()
        flash('تم إضافة المصروف.', 'success')
    except Exception as ex:
        db.session.rollback()
        flash(f'خطأ أثناء الإضافة: {ex}', 'danger')

    return redirect(url_for('admin.expenses'))


@admin_bp.route('/expenses/<int:exp_id>/edit', methods=['POST'])
@login_required
def edit_expense(exp_id):
    try:
        e = Expense.query.get_or_404(exp_id)
        e.description = request.form.get('description', e.description)
        e.amount      = float(request.form.get('amount', e.amount))
        e.date        = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
        e.category_id = request.form.get('category_id') or e.category_id
        e.notes       = request.form.get('notes', e.notes)
        db.session.commit()
        flash('تم تحديث المصروف.', 'success')
    except Exception as ex:
        db.session.rollback()
        flash(f'خطأ أثناء التعديل: {ex}', 'danger')

    return redirect(url_for('admin.expenses'))


@admin_bp.route('/expenses/<int:exp_id>/delete', methods=['POST'])
@login_required
def delete_expense(exp_id):
    try:
        e = Expense.query.get_or_404(exp_id)
        db.session.delete(e)
        db.session.commit()
        flash('تم حذف المصروف.', 'success')
    except Exception as ex:
        db.session.rollback()
        flash(f'خطأ أثناء الحذف: {ex}', 'danger')

    return redirect(url_for('admin.expenses'))


@admin_bp.route('/expenses/export')
@login_required
def export_expenses():
    flash('ميزة التصدير قيد التطوير.', 'info')
    return redirect(url_for('admin.expenses'))
# ════════════════════════════════════════════
# REPORTS
# ════════════════════════════════════════════
@admin_bp.route('/reports')
@login_required
def reports():
    today  = date.today()
    period = request.args.get('period', 'month')

    if period == 'today':
        start = today
    elif period == 'week':
        start = today - timedelta(days=6)
    elif period == 'year':
        start = today.replace(month=1, day=1)
    else:
        start = today.replace(day=1)

    bks = Booking.query.filter(Booking.booking_date >= start).all()
    total_rev  = sum(b.total_price or 0 for b in bks if b.status == 'confirmed')
    total_bks  = len(bks)
    conf_bks   = sum(1 for b in bks if b.status == 'confirmed')
    pend_bks   = sum(1 for b in bks if b.status == 'pending')
    canc_bks   = sum(1 for b in bks if b.status == 'cancelled')
    avg_val    = round(total_rev / conf_bks) if conf_bks else 0
    courts     = Court.query.all()
    court_names   = [c.name for c in courts]
    court_counts  = [Booking.query.filter_by(court_id=c.id, status='confirmed').count() for c in courts]
    court_colors  = [c.color for c in courts]

    top_courts = sorted(
        [{'name': c.name, 'revenue': sum(
            b.total_price or 0 for b in c.bookings if b.status == 'confirmed'
          )} for c in courts],
        key=lambda x: x['revenue'], reverse=True
    )[:5]

    top_products = (db.session.query(Product.name,
                    func.sum(OrderItem.quantity).label('sold'))
                    .join(OrderItem).group_by(Product.id)
                    .order_by(func.sum(OrderItem.quantity).desc())
                    .limit(5).all())

    # Chart labels/data
    labels, bk_data, rev_data = [], [], []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        labels.append(d.strftime('%a'))
        bk_data.append(Booking.query.filter_by(booking_date=d, status='confirmed').count())
        rev_data.append(int(db.session.query(func.sum(Booking.total_price))
                            .filter_by(booking_date=d, status='confirmed').scalar() or 0))

    hourly = [Booking.query.filter(
        Booking.start_time >= datetime.strptime(f'{h:02d}:00', '%H:%M').time(),
        Booking.start_time <  datetime.strptime(f'{(h+1)%24:02d}:00', '%H:%M').time(),
        Booking.status == 'confirmed').count()
        for h in range(24)]

    total_exp  = db.session.query(func.sum(Expense.amount)).scalar() or 0
    total_ords = Order.query.count()
    store_rev  = (db.session.query(func.sum(Order.total_price))
                  .filter_by(status='completed').scalar() or 0)
    total_slots = len(courts) * 18
    booked_today = sum(len(c.today_booked_slots) for c in courts)
    occ_rate = round(booked_today / total_slots * 100) if total_slots else 0

    return render_template('admin/reports.html',
        total_revenue=total_rev, total_bookings=total_bks,
        confirmed_bookings=conf_bks, pending_bookings_count=pend_bks,
        cancelled_bookings=canc_bks, avg_booking_value=avg_val,
        total_orders=total_ords, store_revenue=store_rev,
        total_expenses=total_exp, occupancy_rate=occ_rate,
        chart_labels=labels, bookings_data=bk_data, revenue_data=rev_data,
        hourly_data=hourly,
        court_names=court_names, court_counts=court_counts, court_colors=court_colors,
        top_courts=top_courts,
        top_products=[{'name': p.name, 'sold': p.sold} for p in top_products],
        current_period=period, courts=courts,
    )


@admin_bp.route('/reports/export')
@login_required
def export_report():
    flash('ميزة التصدير قيد التطوير.', 'info')
    return redirect(url_for('admin.reports'))


# ════════════════════════════════════════════
# USERS
# ════════════════════════════════════════════
# ════════════════════════════════════════════
# USERS
# ════════════════════════════════════════════

@admin_bp.route('/users')
@login_required
def users():
    all_users = Admin.query.all()
    return render_template('admin/users.html', users=all_users)


@admin_bp.route('/users/add', methods=['POST'])
@login_required
def add_user():
    if not current_user.has_perm('perm_users'):
        flash('ليس لديك صلاحية لإضافة مستخدمين.', 'danger')
        return redirect(url_for('admin.users'))

    if Admin.query.filter_by(username=request.form['username']).first():
        flash('اسم المستخدم مستخدم بالفعل.', 'danger')
        return redirect(url_for('admin.users'))

    u = Admin(
        username=request.form['username'],
        email=request.form.get('email') or None,
        password=generate_password_hash(request.form['password']),
        role=request.form.get('role', 'staff'),
        is_active=bool(int(request.form.get('is_active', 1))),
        permissions={},
    )
    db.session.add(u)
    db.session.commit()
    flash('تم إضافة المستخدم.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/edit', methods=['POST'])
@login_required
def edit_user(user_id):
    if not current_user.has_perm('perm_users'):
        flash('ليس لديك صلاحية لتعديل المستخدمين.', 'danger')
        return redirect(url_for('admin.users'))

    u = Admin.query.get_or_404(user_id)
    u.username  = request.form.get('username', u.username)
    u.email     = request.form.get('email', u.email) or u.email
    u.role      = request.form.get('role', u.role)
    u.is_active = bool(int(request.form.get('is_active', 1)))
    new_pwd = request.form.get('new_password', '').strip()
    if new_pwd:
        u.password = generate_password_hash(new_pwd)
    db.session.commit()
    flash('تم تحديث المستخدم.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/permissions', methods=['POST'])
@login_required
def edit_permissions(user_id):
    if not current_user.has_perm('perm_users'):
        flash('ليس لديك صلاحية لتعديل الصلاحيات.', 'danger')
        return redirect(url_for('admin.dashboard'))

    # Only superadmin can assign perm_users and perm_settings to others
    perm_keys = ['perm_pos', 'perm_bookings', 'perm_courts', 'perm_products', 'perm_orders',
                 'perm_expenses', 'perm_reports', 'perm_users', 'perm_settings']

    if current_user.role != 'superadmin':
        # non-superadmin cannot grant perm_users or perm_settings
        perm_keys = [k for k in perm_keys if k not in ('perm_users', 'perm_settings')]

    u = Admin.query.get_or_404(user_id)

    # Prevent editing a superadmin's permissions unless you are also superadmin
    if u.role == 'superadmin' and current_user.role != 'superadmin':
        flash('لا يمكنك تعديل صلاحيات المدير العام.', 'danger')
        return redirect(url_for('admin.users'))

    u.permissions = {k: (k in request.form) for k in perm_keys}
    db.session.commit()
    flash('تم تحديث الصلاحيات.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.has_perm('perm_users'):
        flash('ليس لديك صلاحية لحذف المستخدمين.', 'danger')
        return redirect(url_for('admin.users'))

    if user_id == current_user.id:
        flash('لا يمكنك حذف حسابك الخاص.', 'danger')
        return redirect(url_for('admin.users'))

    u = Admin.query.get_or_404(user_id)

    # Prevent deleting a superadmin unless you are also superadmin
    if u.role == 'superadmin' and current_user.role != 'superadmin':
        flash('لا يمكنك حذف حساب المدير العام.', 'danger')
        return redirect(url_for('admin.users'))

    db.session.delete(u)
    db.session.commit()
    flash('تم حذف المستخدم.', 'success')
    return redirect(url_for('admin.users'))


# ════════════════════════════════════════════
# SETTINGS
# ════════════════════════════════════════════
@admin_bp.route('/settings')
@login_required
def settings():
    keys = ['facility_name','phone','email','address','currency',
            'open_time','close_time','allow_midnight_bookings','late_close_time',
            'default_duration','max_advance_days','require_prepayment',
            'auto_confirm','allow_self_cancel','cancel_window_hours',
            'default_price','monthly_budget',
            'store_enabled','min_order_amount','low_stock_alert','pos_enabled',
            'notif_new_booking','notif_cancel_request','notif_new_order',
            'notif_low_stock','notif_pending_review',
            'brand_color','admin_panel_name','enable_animations',
            'show_clock','session_timeout','log_failed_logins']
    cfg = {k: SystemSetting.get(k) for k in keys}
    return render_template('admin/settings.html', settings=cfg)


@admin_bp.route('/settings/save/<section>', methods=['POST'])
@login_required
def save_settings(section):
    for key, val in request.form.items():
        if key == 'csrf_token':
            continue
        SystemSetting.set(key, val)
    # Handle checkboxes (unchecked = not in form)
    checkbox_keys = {
        'general':       ['allow_midnight_bookings'],
        'booking':       ['require_prepayment','auto_confirm','allow_self_cancel'],
        'pricing':       [],
        'store':         ['store_enabled','pos_enabled'],
        'notifications': ['notif_new_booking','notif_cancel_request',
                          'notif_new_order','notif_low_stock','notif_pending_review'],
        'appearance':    ['enable_animations','show_clock'],
        'security':      ['log_failed_logins'],
    }
    for key in checkbox_keys.get(section, []):
        SystemSetting.set(key, 'true' if key in request.form else 'false')
    flash('تم حفظ الإعدادات.', 'success')
    return redirect(url_for('admin.settings'))


# ════════════════════════════════════════════
# DANGER ZONE
# ════════════════════════════════════════════
@admin_bp.route('/danger/delete-cancelled', methods=['POST'])
@login_required
def danger_delete_cancelled():
    Booking.query.filter_by(status='cancelled').delete()
    db.session.commit()
    flash('تم حذف جميع الحجوزات الملغية.', 'success')
    return redirect(url_for('admin.settings'))


@admin_bp.route('/danger/reset-settings', methods=['POST'])
@login_required
def danger_reset_settings():
    SystemSetting.query.delete()
    db.session.commit()
    flash('تم إعادة تعيين الإعدادات.', 'success')
    return redirect(url_for('admin.settings'))


@admin_bp.route('/danger/export-backup')
@login_required
def export_backup():
    flash('ميزة النسخ الاحتياطي قيد التطوير.', 'info')
    return redirect(url_for('admin.settings'))


# ════════════════════════════════════════════
# NOTIFICATIONS API
# ════════════════════════════════════════════
@admin_bp.route('/api/notifications')
@login_required
def api_notifications():
    from flask import jsonify
    from app.models.main import CancelRequest, TrainingRequest
    from app.models.store import Product, Order

    pending_bookings  = Booking.query.filter_by(status='pending').count()
    cancel_requests   = CancelRequest.query.filter_by(status='pending').count()
    training_requests = TrainingRequest.query.filter_by(status='pending').count()
    low_stock         = Product.query.filter(Product.stock <= 5, Product.is_active == True).count()
    pending_orders    = Order.query.filter_by(status='pending').count()

    items = []
    if pending_bookings:
        items.append({
            'icon': 'fa-calendar-clock', 'color': '#FB8C00',
            'en': f'{pending_bookings} pending booking(s) awaiting review',
            'ar': f'يوجد {pending_bookings} حجز بانتظار المراجعة',
            'url': '/admin/pending-bookings'
        })
    if cancel_requests:
        items.append({
            'icon': 'fa-calendar-xmark', 'color': '#E53935',
            'en': f'{cancel_requests} cancellation request(s)',
            'ar': f'يوجد {cancel_requests} طلب إلغاء',
            'url': '/admin/cancel-requests'
        })
    if training_requests:
        items.append({
            'icon': 'fa-dumbbell', 'color': '#7B1FA2',
            'en': f'{training_requests} training request(s)',
            'ar': f'يوجد {training_requests} طلب تدريب',
            'url': '/admin/training-requests'
        })
    if low_stock:
        items.append({
            'icon': 'fa-box-open', 'color': '#F57C00',
            'en': f'{low_stock} product(s) low on stock',
            'ar': f'يوجد {low_stock} منتج ينفد مخزونه',
            'url': '/admin/products'
        })
    if pending_orders:
        items.append({
            'icon': 'fa-bag-shopping', 'color': '#1565C0',
            'en': f'{pending_orders} pending order(s)',
            'ar': f'يوجد {pending_orders} طلب معلق',
            'url': '/admin/orders'
        })

    return jsonify({
        'total': len(items),
        'items': items
    })


# ════════════════════════════════════════════
# MISC
# ════════════════════════════════════════════
@admin_bp.route('/print-barcodes')
@login_required
def print_barcodes():
    products = Product.query.filter(Product.barcode.isnot(None)).all()
    return render_template('admin/print_barcodes.html', products=products)



@admin_bp.route('/coaches')
@login_required
def coaches():
    from app.models.main import Coach
    all_coaches = Coach.query.all()
    return render_template('admin/coaches.html', coaches=all_coaches)


@admin_bp.route('/training-requests')
@login_required
def training_requests():
    from app.models.main import TrainingRequest, Coach
    reqs   = TrainingRequest.query.order_by(TrainingRequest.created_at.desc()).all()
    coaches = Coach.query.filter_by(is_active=True).all()
    return render_template('admin/training_requests.html',
        training_requests=reqs, coaches=coaches)


@admin_bp.route('/coaches/add', methods=['POST'])
@login_required
def add_coach():
    from app.models.main import Coach
    import os
    from werkzeug.utils import secure_filename

    # Handle image upload
    image_path = None
    if 'image' in request.files and request.files['image'].filename != '':
        file = request.files['image']
        if file:
            filename = secure_filename(file.filename)
            # Save to static/uploads/coaches/
            upload_dir = os.path.join('app/static/uploads/coaches')
            os.makedirs(upload_dir, exist_ok=True)
            file.save(os.path.join(upload_dir, filename))
            image_path = f'uploads/coaches/{filename}'  # ✅ Store relative path

    c = Coach(
        name=request.form['name'],
        phone=request.form.get('phone', ''),
        specialty=request.form.get('specialty', ''),
        price_per_hour=float(request.form.get('price_per_hour', 0)),
        bio=request.form.get('bio', ''),
        image=image_path,
        is_active=bool(int(request.form.get('is_active', 1))),
        instagram=request.form.get('instagram', '') or None,
        facebook=request.form.get('facebook', '') or None,
        whatsapp=request.form.get('whatsapp', '') or None,
        tiktok=request.form.get('tiktok', '') or None,
    )
    db.session.add(c)
    db.session.commit()
    flash('تم إضافة المدرب.', 'success')
    return redirect(url_for('admin.coaches'))


@admin_bp.route('/coaches/<int:coach_id>/edit', methods=['POST'])
@login_required
def edit_coach(coach_id):
    from app.models.main import Coach
    import os
    from werkzeug.utils import secure_filename

    c = Coach.query.get_or_404(coach_id)

    # Handle new image if uploaded
    if 'image' in request.files and request.files['image'].filename != '':
        file = request.files['image']
        filename = secure_filename(file.filename)
        upload_dir = os.path.join('app/static/uploads/coaches')
        os.makedirs(upload_dir, exist_ok=True)
        file.save(os.path.join(upload_dir, filename))
        c.image = f'uploads/coaches/{filename}'

    c.name          = request.form.get('name', c.name)
    c.phone         = request.form.get('phone', c.phone)
    c.specialty     = request.form.get('specialty', c.specialty)
    c.price_per_hour = float(request.form.get('price_per_hour', c.price_per_hour))
    c.bio           = request.form.get('bio', c.bio)
    c.is_active     = bool(int(request.form.get('is_active', 1)))
    c.instagram     = request.form.get('instagram', '') or None
    c.facebook      = request.form.get('facebook', '') or None
    c.whatsapp      = request.form.get('whatsapp', '') or None
    c.tiktok        = request.form.get('tiktok', '') or None
    db.session.commit()
    flash('تم تحديث المدرب.', 'success')
    return redirect(url_for('admin.coaches'))
@admin_bp.route('/coaches/<int:coach_id>/delete', methods=['POST'])
@login_required
def delete_coach(coach_id):
    from app.models.main import Coach
    c = Coach.query.get_or_404(coach_id)
    # Nullify FK on related training requests if column exists
    try:
        db.session.execute(
            db.text('UPDATE training_request SET coach_id = NULL WHERE coach_id = :cid'),
            {'cid': coach_id}
        )
    except Exception:
        db.session.rollback()
    db.session.delete(c)
    db.session.commit()
    flash('تم حذف المدرب.', 'success')
    return redirect(url_for('admin.coaches'))


@admin_bp.route('/training-requests/add', methods=['POST'])
def add_training_request():  # ✅ REMOVED @login_required (public form)
    from app.models.main import TrainingRequest
    from datetime import datetime

    # ✅ Validate coach_id is provided
    coach_id = request.form.get('coach_id')
    if not coach_id:
        flash('يرجى اختيار مدرب.', 'error')
        return redirect(request.referrer or url_for('main.index'))

    try:
        tr = TrainingRequest(
            customer_name=request.form['customer_name'],
            customer_phone=request.form['customer_phone'],
            coach_id=int(coach_id),  # ✅ Convert to int
            preferred_date=datetime.strptime(request.form['preferred_date'], '%Y-%m-%d').date() if request.form.get(
                'preferred_date') else None,
            preferred_time=datetime.strptime(request.form['preferred_time'], '%H:%M').time() if request.form.get(
                'preferred_time') else None,
            status=request.form.get('status', 'pending'),
            notes=request.form.get('notes', ''),
        )
        db.session.add(tr)
        db.session.commit()
        flash('تم إرسال طلب التدريب! سنتواصل معك قريباً.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('حدث خطأ أثناء إرسال الطلب.', 'error')

    # ✅ Redirect back to main, not admin
    return redirect(request.referrer or url_for('main.index'))


@admin_bp.route('/training-requests/<int:req_id>/confirm', methods=['POST'])
@login_required  # ✅ Keep this (admin only)
def confirm_training(req_id):
    from app.models.main import TrainingRequest
    tr = TrainingRequest.query.get_or_404(req_id)
    tr.status = 'confirmed'
    db.session.commit()
    flash('تم تأكيد طلب التدريب.', 'success')
    return redirect(url_for('admin.training_requests'))


@admin_bp.route('/training-requests/<int:req_id>/cancel', methods=['POST'])
@login_required  # ✅ Keep this (admin only)
def cancel_training(req_id):
    from app.models.main import TrainingRequest
    tr = TrainingRequest.query.get_or_404(req_id)
    tr.status = 'cancelled'
    db.session.commit()
    flash('تم إلغاء طلب التدريب.', 'success')
    return redirect(url_for('admin.training_requests'))


@admin_bp.route('/courts/new', methods=['GET', 'POST'])
@login_required
def new_court():
    if request.method == 'POST':
        img = save_upload(request.files.get('image'))
        court = Court(
            name=request.form['name'],
            price_per_hour=float(request.form.get('price_per_hour', 25000)),
            color=request.form.get('color', '#1565C0'),
            description=request.form.get('description', ''),
            capacity=request.form.get('capacity') or None,
            surface_type=request.form.get('surface_type', ''),
            is_active=True,
            image=img,
        )
        db.session.add(court)
        db.session.commit()
        flash('تم إضافة الملعب بنجاح.', 'success')
        return redirect(url_for('admin.courts'))
    return render_template('admin/add_court.html')

@admin_bp.route('/categories/<int:cat_id>/edit', methods=['POST'])
@login_required
def edit_category(cat_id):
    from sqlalchemy.exc import IntegrityError
    cat = Category.query.get_or_404(cat_id)
    cat.name          = request.form.get('name', cat.name).strip()
    cat.color         = request.form.get('color', cat.color)
    cat.show_in_store = request.form.get('show_in_store') == '1'
    try:
        db.session.commit()
        flash('تم تحديث الفئة.', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('فئة بهذا الاسم موجودة مسبقاً. / A category with this name already exists.', 'danger')
    return redirect(url_for('admin.categories'))


# ════════════════════════════════════════════
# GAME CLIPS  (NVR ISAPI download)
# ════════════════════════════════════════════

# Court → NVR channel mapping
COURT_CHANNELS = {'court1': 12, 'court2': 15}


def _set_clip_status(app, clip_id, status, msg=None):
    with app.app_context():
        from app.models.main import GameClip
        clip = GameClip.query.get(clip_id)
        if clip:
            clip.status     = status
            clip.status_msg = msg
            db.session.commit()


def _apply_watermark(app, clip_id, raw_path, final_path):
    """
    Overlay a Coda Agency footer on the clip using FFmpeg.
    Falls back to the raw file if FFmpeg is unavailable or fails.
    """
    import subprocess
    logo_path = os.path.join(app.static_folder, 'uploads', 'coaches', 'coda-logo.png')

    if not os.path.exists(logo_path):
        os.replace(raw_path, final_path)
        _set_clip_status(app, clip_id, 'ready')
        return

    _set_clip_status(app, clip_id, 'processing', 'Adding Coda Agency watermark…')

    # Footer bar (52px) + logo bottom-right + text bottom-left
    vf = (
        '[1:v]scale=110:-1:flags=lanczos,format=rgba,colorchannelmixer=aa=0.90[logo];'
        '[0:v]drawbox=x=0:y=ih-52:w=iw:h=52:color=black@0.55:t=fill[bg];'
        '[bg][logo]overlay=W-w-12:H-h-8[vid];'
        "[vid]drawtext=text='Coda Agency':"
        'fontsize=21:fontcolor=white:'
        'x=14:y=H-32:'
        'shadowcolor=black@0.8:shadowx=1:shadowy=1[out]'
    )
    cmd = [
        'ffmpeg', '-y',
        '-i', raw_path,
        '-i', logo_path,
        '-filter_complex', vf,
        '-map', '[out]', '-map', '0:a?',
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23',
        '-c:a', 'copy',
        '-movflags', '+faststart',
        final_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=7200)
        if result.returncode == 0 and os.path.exists(final_path) and os.path.getsize(final_path) > 10_000:
            os.remove(raw_path)
            _set_clip_status(app, clip_id, 'ready')
        else:
            stderr = (result.stderr or b'').decode('utf-8', errors='replace')[-300:]
            os.replace(raw_path, final_path)
            _set_clip_status(app, clip_id, 'ready', f'Watermark failed (ffmpeg rc={result.returncode}): {stderr}')
    except Exception as e:
        if os.path.exists(raw_path):
            os.replace(raw_path, final_path)
        _set_clip_status(app, clip_id, 'ready', f'Watermark skipped: {str(e)[:200]}')


def _download_nvr_clip(app, clip_id, channel, start_dt, end_dt, output_path):
    """Background thread: search NVR recordings and stream to output_path."""
    import threading, requests as req, xml.etree.ElementTree as ET, re
    from requests.auth import HTTPDigestAuth

    with app.app_context():
        nvr_url  = app.config.get('NVR_URL',  'http://45.81.147.210:65021')
        nvr_user = app.config.get('NVR_USER', 'admin')
        nvr_pass = app.config.get('NVR_PASS', 'caMera12')
        auth     = HTTPDigestAuth(nvr_user, nvr_pass)
        track_id = f"{channel}01"  # e.g. 1501 for ch15

        # Times for ISAPI (local Kurdistan time UTC+3)
        start_iso = start_dt.strftime('%Y-%m-%dT%H:%M:%S') + '+03:00'
        end_iso   = end_dt.strftime('%Y-%m-%dT%H:%M:%S')   + '+03:00'
        # Times for playbackURI params (UTC)
        start_utc = (start_dt - timedelta(hours=3)).strftime('%Y%m%dT%H%M%SZ')
        end_utc   = (end_dt   - timedelta(hours=3)).strftime('%Y%m%dT%H%M%SZ')

        search_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<CMSearchDescription xmlns="http://www.std-cgi.com/ver20/XMLSchema/1.0">'
            f'<searchID>{str(uuid.uuid4()).upper()}</searchID>'
            '<trackList>'
            f'<trackID>{track_id}</trackID>'
            '</trackList>'
            '<timeSpanList>'
            '<timeSpan>'
            f'<startTime>{start_iso}</startTime>'
            f'<endTime>{end_iso}</endTime>'
            '</timeSpan>'
            '</timeSpanList>'
            '<maxResults>50</maxResults>'
            '<searchResultPosition>0</searchResultPosition>'
            '<metadataList>'
            '<metadataDescriptor>//recordType.meta.std-cgi.com</metadataDescriptor>'
            '</metadataList>'
            '</CMSearchDescription>'
        )

        try:
            # 1 ── Search for recordings
            r = req.post(
                f"{nvr_url}/ISAPI/ContentMgmt/search",
                data=search_xml.encode('utf-8'),
                headers={'Content-Type': 'text/xml; charset=UTF-8'},
                auth=auth, timeout=30
            )
            if r.status_code != 200:
                _set_clip_status(app, clip_id, 'failed',
                    f"NVR search HTTP {r.status_code}: {r.text[:600]}")
                return

            # 2 ── Extract any playbackURI from the XML (namespace-agnostic)
            root = ET.fromstring(r.text)
            playback_uri = None
            for el in root.iter():
                tag = el.tag.split('}')[-1]   # strip namespace
                if tag == 'playbackURI' and el.text:
                    playback_uri = el.text.strip()
                    break

            if not playback_uri:
                _set_clip_status(app, clip_id, 'failed',
                    f"No recordings found for this time range. "
                    f"Track {track_id} · {start_iso} → {end_iso}. "
                    f"NVR raw: {r.text[:400]}")
                return

            # 3 ── Use the playbackURI as-is from the search result.
            # The search was already scoped to our exact time window, so the URI
            # already points to the right segment. Modifying starttime/endtime
            # parameters in the URI can cause 400 on some firmware versions.
            uri = playback_uri

            # 4 ── Download — pass URI raw in the URL string (don't let requests
            # percent-encode it a second time, which confuses the NVR HTTP parser).
            import urllib.parse as _urlparse
            download_url = (
                f"{nvr_url}/ISAPI/ContentMgmt/download"
                f"?playbackURI={_urlparse.quote(uri, safe=':/@?=&+')}"
            )
            r2 = req.get(download_url, auth=auth, timeout=3600, stream=True)
            if r2.status_code != 200:
                _set_clip_status(app, clip_id, 'failed',
                    f"NVR download HTTP {r2.status_code} "
                    f"· URI={uri[:200]} "
                    f"· resp={r2.text[:300]}")
                return

            # Stream to a _raw temp file; watermark step renames it to final path
            raw_path = output_path.replace('.mp4', '_raw.mp4')
            written = 0
            with open(raw_path, 'wb') as f:
                for chunk in r2.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        written += len(chunk)

            if written < 10_000:
                if os.path.exists(raw_path):
                    os.remove(raw_path)
                _set_clip_status(app, clip_id, 'failed',
                    f"Downloaded file only {written} bytes — NVR may have returned an error page")
                return

            # Apply Coda Agency footer watermark (sets status to 'ready' when done)
            _apply_watermark(app, clip_id, raw_path, output_path)

        except Exception as e:
            _set_clip_status(app, clip_id, 'failed', str(e)[:500])


@admin_bp.route('/clips')
@login_required
def clips():
    all_clips = GameClip.query.order_by(GameClip.created_at.desc()).all()
    return render_template('admin/clips.html', clips=all_clips)


@admin_bp.route('/clips/save', methods=['POST'])
@login_required
def save_clip():
    import threading
    court      = request.form.get('court', '').strip()
    date_str   = request.form.get('clip_date', '').strip()
    start_time = request.form.get('start_time', '').strip()
    end_time   = request.form.get('end_time', '').strip()
    cust_name  = request.form.get('customer_name', '').strip()
    cust_phone = request.form.get('customer_phone', '').strip()
    note       = request.form.get('note', '').strip()

    if court not in COURT_CHANNELS:
        flash('يرجى اختيار ملعب صحيح', 'danger')
        return redirect(url_for('admin.clips'))

    try:
        sfmt = "%Y-%m-%d %H:%M:%S" if start_time.count(':') == 2 else "%Y-%m-%d %H:%M"
        efmt = "%Y-%m-%d %H:%M:%S" if end_time.count(':') == 2 else "%Y-%m-%d %H:%M"
        start_dt = datetime.strptime(f"{date_str} {start_time}", sfmt)
        end_dt   = datetime.strptime(f"{date_str} {end_time}",   efmt)
        if end_dt <= start_dt:
            flash('وقت النهاية يجب أن يكون بعد وقت البداية / End time must be after start time', 'danger')
            return redirect(url_for('admin.clips'))
    except ValueError:
        flash('تنسيق التاريخ أو الوقت غير صحيح', 'danger')
        return redirect(url_for('admin.clips'))

    duration = int((end_dt - start_dt).total_seconds())

    clips_dir = current_app.config['CLIPS_FOLDER']
    os.makedirs(clips_dir, exist_ok=True)

    token    = str(uuid.uuid4())
    filename = f"clip_{token[:8]}.mp4"
    output_path = os.path.join(clips_dir, filename)

    clip = GameClip(
        court=court,
        clip_date=start_dt.date(),
        start_time=start_time,
        duration_sec=duration,
        customer_name=cust_name or None,
        customer_phone=cust_phone or None,
        note=note or None,
        filename=filename,
        token=token,
        status='processing',
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    db.session.add(clip)
    db.session.commit()

    channel = COURT_CHANNELS[court]
    app = current_app._get_current_object()
    t = threading.Thread(
        target=_download_nvr_clip,
        args=(app, clip.id, channel, start_dt, end_dt, output_path),
        daemon=True
    )
    t.start()

    flash('⏳ جاري تحميل المقطع من NVR — سيظهر جاهزاً خلال دقائق. / Clip is downloading from NVR — will be ready in a few minutes.', 'info')
    return redirect(url_for('admin.clips'))


@admin_bp.route('/clips/<int:clip_id>/download')
@login_required
def download_admin_clip(clip_id):
    clip = GameClip.query.get_or_404(clip_id)
    filepath = os.path.join(current_app.config['CLIPS_FOLDER'], clip.filename)
    if not os.path.exists(filepath):
        flash('الملف غير موجود على السيرفر', 'danger')
        return redirect(url_for('admin.clips'))
    return send_file(filepath, as_attachment=True,
                     download_name=f"padel-{clip.court}-{clip.clip_date}.mp4",
                     mimetype='video/mp4')


@admin_bp.route('/clips/<int:clip_id>/delete', methods=['POST'])
@login_required
def delete_clip(clip_id):
    clip = GameClip.query.get_or_404(clip_id)
    filepath = os.path.join(current_app.config['CLIPS_FOLDER'], clip.filename or '')
    if filepath and os.path.exists(filepath):
        try:
            os.remove(filepath)
        except OSError:
            pass
    db.session.delete(clip)
    db.session.commit()
    flash('تم حذف المقطع', 'success')
    return redirect(url_for('admin.clips'))

# ════════════════════════════════════════════
# ACTIVITY TABLES  (Snooker / Billiard / Table Tennis)
# ════════════════════════════════════════════

@admin_bp.route('/activity-tables')
@login_required
def activity_tables():
    tables   = ActivityTable.query.order_by(ActivityTable.activity, ActivityTable.name).all()
    sessions = ActivitySession.query.order_by(ActivitySession.created_at.desc()).limit(50).all()
    return render_template('admin/activity_tables.html',
                           tables=tables, sessions=sessions,
                           activity_meta=ACTIVITY_META,
                           activities_order=['snooker', 'billiard', 'table_tennis', 'spectator'])


@admin_bp.route('/activity-tables/add', methods=['POST'])
@login_required
def add_activity_table():
    name        = (request.form.get('name') or '').strip()
    activity    = request.form.get('activity', '').strip()
    hourly_rate = float(request.form.get('hourly_rate', 0) or 0)
    if not name or activity not in ACTIVITY_META:
        flash('Invalid data', 'danger')
        return redirect(url_for('admin.activity_tables'))
    db.session.add(ActivityTable(name=name, activity=activity, hourly_rate=hourly_rate))
    db.session.commit()
    flash('Table added successfully', 'success')
    return redirect(url_for('admin.activity_tables'))


@admin_bp.route('/activity-tables/<int:table_id>/edit', methods=['POST'])
@login_required
def edit_activity_table(table_id):
    table = ActivityTable.query.get_or_404(table_id)
    table.name        = (request.form.get('name') or table.name).strip()
    table.hourly_rate = float(request.form.get('hourly_rate', table.hourly_rate) or 0)
    table.is_active   = request.form.get('is_active') == '1'
    db.session.commit()
    flash('Table updated', 'success')
    return redirect(url_for('admin.activity_tables'))


@admin_bp.route('/activity-tables/<int:table_id>/delete', methods=['POST'])
@login_required
def delete_activity_table(table_id):
    table = ActivityTable.query.get_or_404(table_id)
    if ActivitySession.query.filter_by(table_id=table_id, status='active').first():
        flash('Cannot delete — table has an active session', 'danger')
        return redirect(url_for('admin.activity_tables'))
    db.session.delete(table)
    db.session.commit()
    flash('Table deleted', 'success')
    return redirect(url_for('admin.activity_tables'))


# ════════════════════════════════════════════
# SPONSORS
# ════════════════════════════════════════════
@admin_bp.route('/cameras')
@login_required
def cameras():
    nvr_url = current_app.config.get('NVR_URL', 'http://45.81.147.210:65021')
    return render_template('admin/cameras.html', nvr_url=nvr_url)


@admin_bp.route('/cameras/snapshot/<int:channel>')
@login_required
def camera_snapshot(channel):
    """Proxy a JPEG snapshot from the Hikvision NVR ISAPI — bypasses X-Frame-Options."""
    import requests as req
    from requests.auth import HTTPDigestAuth
    from flask import Response
    if channel not in range(1, 33):
        return Response(status=400)
    nvr_url  = current_app.config.get('NVR_URL',  'http://45.81.147.210:65021')
    nvr_user = current_app.config.get('NVR_USER', 'admin')
    nvr_pass = current_app.config.get('NVR_PASS', 'caMera12')
    api_url  = f"{nvr_url}/ISAPI/Streaming/channels/{channel}01/picture"
    try:
        # Hikvision uses Digest Auth by default
        r = req.get(api_url, auth=HTTPDigestAuth(nvr_user, nvr_pass), timeout=8, stream=False)
        if r.status_code == 200:
            resp = Response(r.content, mimetype='image/jpeg')
            resp.headers['Cache-Control'] = 'no-store'
            return resp
        return Response(f"NVR returned {r.status_code}", status=r.status_code)
    except req.exceptions.ConnectTimeout:
        return Response("NVR connect timeout", status=504)
    except req.exceptions.ConnectionError as e:
        return Response(f"NVR connection error: {e}", status=503)
    except Exception as e:
        return Response(f"Error: {e}", status=500)


@admin_bp.route('/cameras/debug')
@login_required
def cameras_debug():
    """Test NVR connectivity and return status as JSON."""
    import requests as req
    from requests.auth import HTTPDigestAuth
    nvr_url  = current_app.config.get('NVR_URL',  'http://45.81.147.210:65021')
    nvr_user = current_app.config.get('NVR_USER', 'admin')
    nvr_pass = current_app.config.get('NVR_PASS', 'caMera12')
    results = {}
    for ch in [1, 2]:
        url = f"{nvr_url}/ISAPI/Streaming/channels/{ch}01/picture"
        try:
            r = req.get(url, auth=HTTPDigestAuth(nvr_user, nvr_pass), timeout=8)
            results[f"ch{ch}"] = {"status": r.status_code, "content_type": r.headers.get('Content-Type',''), "size": len(r.content)}
        except Exception as e:
            results[f"ch{ch}"] = {"error": str(e)}
    return jsonify({"nvr_url": nvr_url, "user": nvr_user, "results": results})


@admin_bp.route('/sponsors', methods=['GET', 'POST'])
@login_required
def sponsors():
    sponsors = Sponsor.query.order_by(Sponsor.sort_order, Sponsor.created_at).all()
    return render_template('admin/sponsors.html', sponsors=sponsors)


@admin_bp.route('/sponsors/add', methods=['POST'])
@login_required
def add_sponsor():
    name    = request.form.get('name', '').strip()
    website = request.form.get('website', '').strip()
    order   = int(request.form.get('sort_order', 0) or 0)
    logo    = save_upload(request.files.get('logo'), fix_bg=False)
    if not name:
        flash('Name is required.', 'danger')
        return redirect(url_for('admin.sponsors'))
    db.session.add(Sponsor(name=name, logo=logo, website=website or None, sort_order=order))
    db.session.commit()
    flash('Sponsor added.', 'success')
    return redirect(url_for('admin.sponsors'))


@admin_bp.route('/sponsors/<int:sponsor_id>/delete', methods=['POST'])
@login_required
def delete_sponsor(sponsor_id):
    s = Sponsor.query.get_or_404(sponsor_id)
    db.session.delete(s)
    db.session.commit()
    flash('Sponsor deleted.', 'success')
    return redirect(url_for('admin.sponsors'))


@admin_bp.route('/sponsors/<int:sponsor_id>/toggle', methods=['POST'])
@login_required
def toggle_sponsor(sponsor_id):
    s = Sponsor.query.get_or_404(sponsor_id)
    s.is_active = not s.is_active
    db.session.commit()
    return redirect(url_for('admin.sponsors'))
