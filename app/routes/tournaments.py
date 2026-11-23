import csv
import io
import re
import threading
from datetime import datetime, date, timedelta
from functools import wraps

from flask import (Blueprint, render_template, request, redirect, url_for, flash,
                   Response, current_app, abort)
from flask_login import login_required, current_user

from app import db
from app.models.main import Tournament, TournamentRegistration

tournaments_bp = Blueprint('tournaments', __name__)

LEVELS = ('beginner', 'intermediate', 'advanced', 'professional')
STATUSES = ('open', 'closed', 'hidden')
REG_STATUSES = ('pending', 'confirmed', 'cancelled')


def _admin_required(f):
    @wraps(f)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.has_perm('perm_courts'):
            flash('Access denied.', 'danger')
            return redirect(url_for('admin.dashboard'))
        return f(*args, **kwargs)
    return wrapper


def _clean_phone(raw):
    """Keep digits (and a leading +). Returns '' if it doesn't look like a phone number."""
    raw = (raw or '').strip()
    digits = re.sub(r'\D', '', raw)
    if not 7 <= len(digits) <= 15:
        return ''
    return ('+' if raw.startswith('+') else '') + digits


def _parse_date(value):
    try:
        return datetime.strptime((value or '').strip(), '%Y-%m-%d').date()
    except ValueError:
        return None


def _parse_registration(form, tournament):
    """Validate a team registration form. Returns (data, errors)."""
    data = {
        'player1_name':  (form.get('player1_name') or '').strip()[:100],
        'player1_phone': _clean_phone(form.get('player1_phone')),
        'player2_name':  (form.get('player2_name') or '').strip()[:100],
        'player2_phone': _clean_phone(form.get('player2_phone')),
        'team_name':     (form.get('team_name') or '').strip()[:100] or None,
        'category':      (form.get('category') or '').strip()[:80],
        'level':         (form.get('level') or '').strip(),
        'notes':         (form.get('notes') or '').strip()[:500] or None,
    }
    errors = []
    if not data['player1_name'] or not data['player2_name']:
        errors.append('names')
    if not data['player1_phone'] or not data['player2_phone']:
        errors.append('phones')
    elif data['player1_phone'] == data['player2_phone']:
        errors.append('same_phone')
    cats = tournament.category_list
    if cats and data['category'] not in cats:
        errors.append('category')
    if not cats:
        data['category'] = ''
    if data['level'] not in LEVELS:
        errors.append('level')
    if not errors:
        phones = {data['player1_phone'], data['player2_phone']}
        for r in tournament.active_registrations:
            if r.category == data['category'] and phones & {r.player1_phone, r.player2_phone}:
                errors.append('duplicate')
                break
    return data, errors


def _notify_admins(app, title, body, url):
    """Send the push notification in the background so the player isn't kept waiting."""
    def run():
        with app.app_context():
            try:
                from app.routes.admin import _send_push_all
                _send_push_all(title, body, url)
            except Exception:
                current_app.logger.exception('tournament push failed')
    threading.Thread(target=run, daemon=True).start()


# ═══════════════════════════════════════════
# PUBLIC
# ═══════════════════════════════════════════
@tournaments_bp.route('/')
def public_list():
    today = date.today()
    tournaments = (Tournament.query.filter(Tournament.status != 'hidden')
                   .order_by(Tournament.start_date.desc()).all())
    upcoming = sorted([t for t in tournaments if (t.end_date or t.start_date) >= today],
                      key=lambda t: t.start_date)
    past = [t for t in tournaments if (t.end_date or t.start_date) < today]
    return render_template('tournaments/list.html', upcoming=upcoming, past=past, today=today)


@tournaments_bp.route('/<int:tournament_id>', methods=['GET', 'POST'])
def public_detail(tournament_id):
    t = Tournament.query.get_or_404(tournament_id)
    if t.status == 'hidden' and not (current_user.is_authenticated and current_user.has_perm('perm_courts')):
        abort(404)

    errors, form = [], {}
    if request.method == 'POST':
        form = request.form
        if form.get('website'):          # honeypot: real people never fill this hidden field
            return redirect(url_for('tournaments.public_detail', tournament_id=t.id))
        closed = t.registration_closed_reason()
        if closed:
            errors = [closed]
        else:
            data, errors = _parse_registration(form, t)
            if not errors:
                reg = TournamentRegistration(tournament_id=t.id, status='pending', **data)
                db.session.add(reg)
                db.session.commit()
                _notify_admins(current_app._get_current_object(),
                               f'New tournament team — {t.name}',
                               f'{reg.player1_name} & {reg.player2_name}'
                               + (f' ({reg.category})' if reg.category else ''),
                               url_for('tournaments.admin_detail', tournament_id=t.id))
                return redirect(url_for('tournaments.public_detail', tournament_id=t.id,
                                        registered=reg.id) + '#teams')

    registered = request.args.get('registered', type=int)
    return render_template('tournaments/detail.html', tour=t, errors=errors, form=form,
                           closed_reason=t.registration_closed_reason(),
                           registered=registered, levels=LEVELS)


# ═══════════════════════════════════════════
# ADMIN
# ═══════════════════════════════════════════
def _tournament_from_form(t, form):
    """Fill a Tournament from the admin form. Returns an error message or None."""
    name = (form.get('name') or '').strip()
    start = _parse_date(form.get('start_date'))
    if not name or not start:
        return 'Name and start date are required. / الاسم وتاريخ البدء مطلوبان.'
    end = _parse_date(form.get('end_date'))
    if end and end < start:
        return 'End date is before start date. / تاريخ الانتهاء قبل تاريخ البدء.'
    try:
        fee = max(0.0, float(form.get('entry_fee') or 0))
        max_teams = max(0, int(form.get('max_teams') or 0))
    except ValueError:
        return 'Fee and max teams must be numbers. / الرسوم وعدد الفرق يجب أن تكون أرقاماً.'
    start_time = None
    if form.get('start_time'):
        try:
            start_time = datetime.strptime(form['start_time'], '%H:%M').time()
        except ValueError:
            return 'Invalid start time. / وقت البدء غير صحيح.'

    t.name = name[:150]
    t.description = (form.get('description') or '').strip() or None
    t.start_date, t.end_date, t.start_time = start, end, start_time
    t.registration_deadline = _parse_date(form.get('registration_deadline'))
    t.categories = ', '.join(c.strip() for c in (form.get('categories') or '').split(',') if c.strip())
    t.entry_fee, t.max_teams = fee, max_teams
    t.status = form.get('status') if form.get('status') in STATUSES else 'open'
    t.show_teams = form.get('show_teams') == '1'
    return None


@tournaments_bp.route('/admin')
@_admin_required
def admin_list():
    tournaments = Tournament.query.order_by(Tournament.start_date.desc()).all()
    return render_template('tournaments/admin_list.html', tournaments=tournaments, today=date.today())


@tournaments_bp.route('/admin/new', methods=['POST'])
@_admin_required
def admin_create():
    t = Tournament()
    err = _tournament_from_form(t, request.form)
    if err:
        flash(err, 'danger')
        return redirect(url_for('tournaments.admin_list'))
    db.session.add(t)
    db.session.commit()
    flash('تم إنشاء البطولة. / Tournament created.', 'success')
    return redirect(url_for('tournaments.admin_detail', tournament_id=t.id))


@tournaments_bp.route('/admin/<int:tournament_id>')
@_admin_required
def admin_detail(tournament_id):
    t = Tournament.query.get_or_404(tournament_id)
    status_filter = request.args.get('status', 'active')
    category_filter = request.args.get('category', '')
    regs = t.registrations
    if status_filter == 'active':
        regs = [r for r in regs if r.status != 'cancelled']
    elif status_filter in REG_STATUSES:
        regs = [r for r in regs if r.status == status_filter]
    if category_filter:
        regs = [r for r in regs if r.category == category_filter]
    counts = {c: sum(1 for r in t.active_registrations if r.category == c) for c in t.category_list}
    return render_template('tournaments/admin_detail.html', tour=t, regs=regs, counts=counts,
                           status_filter=status_filter, category_filter=category_filter,
                           levels=LEVELS, reg_statuses=REG_STATUSES, statuses=STATUSES)


@tournaments_bp.route('/admin/<int:tournament_id>/edit', methods=['POST'])
@_admin_required
def admin_edit(tournament_id):
    t = Tournament.query.get_or_404(tournament_id)
    err = _tournament_from_form(t, request.form)
    if err:
        db.session.rollback()
        flash(err, 'danger')
    else:
        db.session.commit()
        flash('تم حفظ البطولة. / Tournament saved.', 'success')
    return redirect(url_for('tournaments.admin_detail', tournament_id=t.id))


@tournaments_bp.route('/admin/<int:tournament_id>/delete', methods=['POST'])
@_admin_required
def admin_delete(tournament_id):
    t = Tournament.query.get_or_404(tournament_id)
    db.session.delete(t)
    db.session.commit()
    flash('تم حذف البطولة وتسجيلاتها. / Tournament and its registrations deleted.', 'success')
    return redirect(url_for('tournaments.admin_list'))


@tournaments_bp.route('/admin/<int:tournament_id>/add-team', methods=['POST'])
@_admin_required
def admin_add_team(tournament_id):
    t = Tournament.query.get_or_404(tournament_id)
    data, errors = _parse_registration(request.form, t)
    if errors:
        flash('تحقق من بيانات الفريق. / Check the team details: ' + ', '.join(errors), 'danger')
    else:
        db.session.add(TournamentRegistration(tournament_id=t.id, status='confirmed',
                                              added_by=current_user.username, **data))
        db.session.commit()
        flash('تمت إضافة الفريق. / Team added.', 'success')
    return redirect(url_for('tournaments.admin_detail', tournament_id=t.id))


@tournaments_bp.route('/admin/registration/<int:reg_id>/update', methods=['POST'])
@_admin_required
def admin_update_registration(reg_id):
    r = TournamentRegistration.query.get_or_404(reg_id)
    if request.form.get('status') in REG_STATUSES:
        r.status = request.form['status']
    if 'paid' in request.form:
        r.paid = request.form.get('paid') == '1'
    db.session.commit()
    nxt = request.form.get('next') or ''
    if not (nxt.startswith('/') and not nxt.startswith('//')):   # only redirect within this site
        nxt = url_for('tournaments.admin_detail', tournament_id=r.tournament_id)
    return redirect(nxt)


@tournaments_bp.route('/admin/registration/<int:reg_id>/delete', methods=['POST'])
@_admin_required
def admin_delete_registration(reg_id):
    r = TournamentRegistration.query.get_or_404(reg_id)
    tid = r.tournament_id
    db.session.delete(r)
    db.session.commit()
    flash('تم حذف التسجيل. / Registration deleted.', 'success')
    return redirect(url_for('tournaments.admin_detail', tournament_id=tid))


@tournaments_bp.route('/admin/<int:tournament_id>/export.csv')
@_admin_required
def admin_export(tournament_id):
    t = Tournament.query.get_or_404(tournament_id)
    out = io.StringIO()
    out.write('﻿')  # BOM so Excel shows Arabic/Kurdish names correctly
    w = csv.writer(out)
    w.writerow(['#', 'Registered (local)', 'Category', 'Team', 'Player 1', 'Phone 1', 'Player 2', 'Phone 2',
                'Level', 'Status', 'Paid', 'Notes', 'Added by'])
    for i, r in enumerate(t.registrations, 1):
        w.writerow([i, _local(r.created_at), r.category, r.team_name or '', r.player1_name, r.player1_phone,
                    r.player2_name, r.player2_phone, r.level, r.status, 'yes' if r.paid else 'no',
                    r.notes or '', r.added_by or 'website'])
    filename = re.sub(r'[^A-Za-z0-9_-]+', '_', t.name).strip('_') or f'tournament_{t.id}'
    return Response(out.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename="{filename}_teams.csv"'})


def _local(dt):
    """Stored times are UTC; Duhok is UTC+3."""
    return (dt + timedelta(hours=3)).strftime('%Y-%m-%d %H:%M') if dt else ''


@tournaments_bp.app_template_filter('local_dt')
def local_dt_filter(dt):
    return _local(dt)
