from flask import Blueprint, render_template, session, redirect, request, send_file, jsonify, current_app, send_from_directory, abort
from flask_login import login_required
from app.models.main import Court, Booking, Coach, GameClip, Sponsor
from app.models.store import Product

import os
import subprocess
import tempfile
from datetime import datetime

main_bp = Blueprint('main', __name__)

# عدّل هذا المسار حسب مكان حفظ التسجيلات (محلياً وقت الاختبار، أو مسار الـ VPS لاحقاً)
RECORD_DIR = r"C:\recordings"


@main_bp.route('/set-lang/<lang>')
def set_lang(lang):
    if lang in ('ar', 'en', 'ku'):
        session['lang'] = lang
        session.permanent = True
    return redirect(request.referrer or '/')


@main_bp.route('/')
def loading():
    return render_template('loading.html')


@main_bp.route('/home')
def index():
    # Fetch all data needed for the index.html page
    coaches = Coach.query.filter_by(is_active=True).all()
    courts = Court.query.filter_by(is_active=True).all()
    total_bookings = Booking.query.filter_by(status='confirmed').count()

    # Fetch active products marked for the website, limited to 4
    products = Product.query.filter_by(is_active=True, show_on_website=True).limit(4).all()
    sponsors = Sponsor.query.filter_by(is_active=True).order_by(Sponsor.sort_order, Sponsor.created_at).all()

    return render_template('index.html',
                           coaches=coaches,
                           courts=courts,
                           total_bookings=total_bookings,
                           products=products,
                           sponsors=sponsors)


@main_bp.route('/coaches/<int:coach_id>')
def coach_profile(coach_id):
    coach = Coach.query.get_or_404(coach_id)
    all_coaches = Coach.query.filter_by(is_active=True).all()
    return render_template('coach_profile.html', coach=coach, all_coaches=all_coaches)


@main_bp.route('/coaches/<int:coach_id>/book', methods=['GET', 'POST'])
def coach_book(coach_id):
    from app.models.main import TrainingRequest
    coach = Coach.query.get_or_404(coach_id)
    all_coaches = Coach.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        tr = TrainingRequest(
            coach_id=int(request.form.get('coach_id', coach_id)),
            customer_name=request.form.get('customer_name', '').strip(),
            customer_phone=request.form.get('customer_phone', '').strip(),
            package=request.form.get('package', ''),
            playing_level=request.form.get('playing_level', ''),
            notes=request.form.get('note', '').strip(),
            status='pending',
        )
        from app import db
        db.session.add(tr)
        db.session.commit()
        return render_template('coach_book_success.html', coach=coach)

    return render_template('coach_book.html', coach=coach, all_coaches=all_coaches)


@main_bp.route('/sw.js')
def sw():
    return send_from_directory(current_app.static_folder, 'sw.js'), 200, {'Content-Type': 'application/javascript'}


@main_bp.route('/download-clip', methods=['POST'])
def download_clip():
    court = request.form.get("court")
    date_str = request.form.get("date")
    start_time = request.form.get("start_time")
    duration = int(request.form.get("duration", 30))

    if court not in ("court1", "court2"):
        return jsonify({"message": "ملعب غير صحيح"}), 400

    try:
        requested_dt = datetime.strptime(f"{date_str} {start_time}", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return jsonify({"message": "تنسيق التاريخ أو الوقت غير صحيح"}), 400

    court_dir = os.path.join(RECORD_DIR, court)
    if not os.path.isdir(court_dir):
        return jsonify({"message": "لا يوجد تسجيلات لهذا الملعب"}), 404

    files = sorted(f for f in os.listdir(court_dir) if f.endswith(".mp4"))

    target_file, file_start_dt = None, None
    for f in files:
        try:
            f_dt = datetime.strptime(f.replace(".mp4", ""), "%Y-%m-%d_%H-%M-%S")
        except ValueError:
            continue
        if f_dt <= requested_dt:
            target_file, file_start_dt = f, f_dt
        else:
            break

    if not target_file:
        return jsonify({"message": "لا يوجد تسجيل لهذا الوقت"}), 404

    offset_seconds = (requested_dt - file_start_dt).total_seconds()
    input_path = os.path.join(court_dir, target_file)

    output_fd, output_path = tempfile.mkstemp(suffix=".mp4")
    os.close(output_fd)

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(offset_seconds),
        "-i", input_path,
        "-t", str(duration),
        "-c", "copy",
        output_path
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=30)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return jsonify({"message": "فشل استخراج المقطع"}), 500

    return send_file(
        output_path,
        as_attachment=True,
        download_name=f"padel-{court}-{date_str}.mp4",
        mimetype="video/mp4"
    )


_PUBLIC_COURT_CHANNELS = {'court1': 15, 'court2': 12}

@main_bp.route('/live-snapshot/<court>')
@login_required
def live_snapshot(court):
    """Public blurred snapshot proxy — only court1 / court2 allowed, no login required."""
    from flask import Response
    import requests as req
    from requests.auth import HTTPDigestAuth
    channel = _PUBLIC_COURT_CHANNELS.get(court)
    if not channel:
        return Response(status=404)
    nvr_url  = current_app.config.get('NVR_URL',  'http://45.81.147.210:65021')
    nvr_user = current_app.config.get('NVR_USER', 'admin')
    nvr_pass = current_app.config.get('NVR_PASS', 'caMera12')
    try:
        r = req.get(
            f"{nvr_url}/ISAPI/Streaming/channels/{channel}01/picture",
            auth=HTTPDigestAuth(nvr_user, nvr_pass),
            timeout=8,
        )
        if r.status_code == 200:
            resp = Response(r.content, mimetype='image/jpeg')
            resp.headers['Cache-Control'] = 'no-store'
            return resp
        return Response(status=503)
    except Exception:
        return Response(status=503)


@main_bp.route('/clip/<token>')
def share_clip(token):
    clip = GameClip.query.filter_by(token=token).first_or_404()
    if clip.is_expired:
        return render_template('clip_expired.html'), 410
    if not clip.filename:
        abort(404)
    filepath = os.path.join(current_app.config['CLIPS_FOLDER'], clip.filename)
    if not os.path.isfile(filepath):
        abort(404)
    return render_template('clip_share.html', clip=clip)


@main_bp.route('/clip/<token>/stream')
def stream_clip_file(token):
    """Serve video inline with range-request support for mobile browsers."""
    clip = GameClip.query.filter_by(token=token).first_or_404()
    if clip.is_expired:
        abort(410)
    if not clip.filename:
        abort(404)
    filepath = os.path.join(current_app.config['CLIPS_FOLDER'], clip.filename)
    if not os.path.isfile(filepath):
        abort(404)
    return send_file(
        filepath,
        mimetype="video/mp4",
        conditional=True,
    )


@main_bp.route('/clip/<token>/download')
def download_clip_file(token):
    clip = GameClip.query.filter_by(token=token).first_or_404()
    if clip.is_expired:
        return render_template('clip_expired.html'), 410
    filepath = os.path.join(current_app.config['CLIPS_FOLDER'], clip.filename or '')
    if not os.path.exists(filepath):
        abort(404)
    return send_file(
        filepath,
        as_attachment=True,
        download_name=f"padel-{clip.court}-{clip.clip_date}.mp4",
        mimetype="video/mp4"
    )