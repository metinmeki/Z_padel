from flask import Blueprint, render_template, session, redirect, request, send_file, jsonify, current_app, send_from_directory, abort
from app.models.main import Court, Booking, Coach, GameClip
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

    return render_template('index.html',
                           coaches=coaches,
                           courts=courts,
                           total_bookings=total_bookings,
                           products=products)


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


@main_bp.route('/clip/<token>')
def share_clip(token):
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