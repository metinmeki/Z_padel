import csv
import io
import re
import secrets
import threading
from datetime import datetime, date, timedelta
from functools import wraps

from flask import (Blueprint, render_template, request, redirect, url_for, flash,
                   Response, current_app, abort)
from flask_login import login_required, current_user

from app import db
from app.models.main import Tournament, TournamentRegistration, TournamentMatch

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


def featured_bracket_tournament():
    """The soonest upcoming/ongoing public tournament that has a bracket, for the home page."""
    today = date.today()
    drawn = (Tournament.query.filter(Tournament.status != 'hidden')
             .join(TournamentMatch).distinct().order_by(Tournament.start_date).all())
    return next((t for t in drawn if (t.end_date or t.start_date) >= today), None)


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
    # Take the team out of any bracket first, so no match points at a deleted team
    for m in TournamentMatch.query.filter(
            (TournamentMatch.team1_id == r.id) | (TournamentMatch.team2_id == r.id)).all():
        b = _Bracket(r.tournament, m.category)
        m = b.get(m.round, m.position)
        if m.team1_id == r.id:
            m.team1_id = None
        if m.team2_id == r.id:
            m.team2_id = None
        if m.winner_id == r.id:
            b.set_result(m, None, force=True)
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


# ═══════════════════════════════════════════
# BRACKET (single elimination, one per category)
# ═══════════════════════════════════════════
class _Bracket:
    """The matches of one tournament category, keyed by (round, position)."""

    def __init__(self, tournament, category):
        self.t, self.category = tournament, category
        self.matches = {(m.round, m.position): m for m in tournament.matches if m.category == category}
        self.rounds = max((r for r, _ in self.matches), default=0)

    def get(self, rnd, pos):
        return self.matches[(rnd, pos)]

    def _feed_next(self, match, team_id):
        """Put a match's winner (or None) into its slot in the next round, undoing later results it invalidates."""
        if match.round >= self.rounds:
            return
        nxt = self.get(match.round + 1, match.position // 2)
        slot = 'team1_id' if match.position % 2 == 0 else 'team2_id'
        if getattr(nxt, slot) == team_id:
            return
        setattr(nxt, slot, team_id)
        if nxt.winner_id is not None:
            nxt.winner_id, nxt.score = None, None
            self._feed_next(nxt, None)

    def set_result(self, match, winner_id, score=None, force=False):
        """winner_id None clears the result. Returns an error code or None."""
        if match.is_bye and not force:
            return 'bye'
        if winner_id is not None:
            if not (match.team1_id and match.team2_id):
                return 'waiting'
            if winner_id not in (match.team1_id, match.team2_id):
                return 'winner'
        match.winner_id = winner_id
        match.score = ((score or '').strip()[:60] or None) if winner_id else None
        self._feed_next(match, winner_id)
        return None

    @classmethod
    def draw(cls, tournament, category, team_ids):
        """Shuffle the teams into a fresh bracket, replacing any existing one for this category."""
        TournamentMatch.query.filter_by(tournament_id=tournament.id, category=category).delete()
        db.session.flush()
        db.session.expire(tournament, ['matches'])

        teams = list(team_ids)
        secrets.SystemRandom().shuffle(teams)
        size = 2
        while size < len(teams):
            size *= 2
        first_round = size // 2
        byes = size - len(teams)
        # spread the byes evenly so they don't all land in one half of the bracket
        bye_positions = {k * first_round // byes for k in range(byes)} if byes else set()

        it = iter(teams)
        rnd, count = 1, first_round
        while count >= 1:
            for pos in range(count):
                m = TournamentMatch(tournament_id=tournament.id, category=category, round=rnd, position=pos)
                if rnd == 1:
                    m.team1_id = next(it)
                    if pos in bye_positions:
                        m.is_bye = True
                    else:
                        m.team2_id = next(it)
                db.session.add(m)
            rnd, count = rnd + 1, count // 2
        db.session.flush()
        db.session.expire(tournament, ['matches'])

        b = cls(tournament, category)
        for pos in sorted(bye_positions):
            m = b.get(1, pos)
            m.winner_id = m.team1_id
            b._feed_next(m, m.team1_id)
        return b


def round_key(rnd, total):
    """'final', 'semi', 'quarter' or the number of teams in that round (16, 32…)."""
    left = total - rnd
    return {0: 'final', 1: 'semi', 2: 'quarter'}.get(left, 2 ** (left + 1))


@tournaments_bp.app_template_global()
def bracket_for(tournament, category):
    """Rounds of a category's bracket for templates: [(round_key, [matches])], or [] if not drawn."""
    ms = [m for m in tournament.matches if m.category == category]
    total = max((m.round for m in ms), default=0)
    return [(round_key(r, total), [m for m in ms if m.round == r]) for r in range(1, total + 1)]


@tournaments_bp.route('/admin/<int:tournament_id>/draw', methods=['POST'])
@_admin_required
def admin_draw(tournament_id):
    t = Tournament.query.get_or_404(tournament_id)
    category = request.form.get('category', '')
    if t.category_list and category not in t.category_list:
        abort(400)
    allowed = ('confirmed', 'pending') if request.form.get('include_pending') == '1' else ('confirmed',)
    team_ids = [r.id for r in t.registrations if r.category == category and r.status in allowed]
    if len(team_ids) < 2:
        flash('تحتاج إلى فريقين مؤكدين على الأقل للقرعة. / You need at least 2 confirmed teams to make the draw.', 'danger')
    else:
        _Bracket.draw(t, category, team_ids)
        db.session.commit()
        flash(f'تمت القرعة. / Draw done: {len(team_ids)} teams' + (f' ({category})' if category else '') + '.', 'success')
    return redirect(url_for('tournaments.admin_detail', tournament_id=t.id) + '#bracket')


@tournaments_bp.route('/admin/<int:tournament_id>/bracket/delete', methods=['POST'])
@_admin_required
def admin_delete_bracket(tournament_id):
    t = Tournament.query.get_or_404(tournament_id)
    TournamentMatch.query.filter_by(tournament_id=t.id, category=request.form.get('category', '')).delete()
    db.session.commit()
    flash('تم حذف الجدول. / Bracket deleted.', 'success')
    return redirect(url_for('tournaments.admin_detail', tournament_id=t.id) + '#bracket')


@tournaments_bp.route('/admin/match/<int:match_id>/result', methods=['POST'])
@_admin_required
def admin_match_result(match_id):
    m = TournamentMatch.query.get_or_404(match_id)
    b = _Bracket(m.tournament, m.category)
    m = b.get(m.round, m.position)
    winner = request.form.get('winner', type=int)       # a team id, or missing/0 to clear
    err = b.set_result(m, winner or None, request.form.get('score'))
    if err:
        flash({'bye': 'هذه المباراة تأهل مباشر. / This is a bye.',
               'waiting': 'المباراة بانتظار الفريقين. / Both teams are not known yet.',
               'winner': 'الفائز غير صحيح. / Invalid winner.'}[err], 'danger')
        db.session.rollback()
    else:
        db.session.commit()
    return redirect(url_for('tournaments.admin_detail', tournament_id=m.tournament_id) + f'#match-{m.id}')


def _local(dt):
    """Stored times are UTC; Duhok is UTC+3."""
    return (dt + timedelta(hours=3)).strftime('%Y-%m-%d %H:%M') if dt else ''


@tournaments_bp.app_template_filter('local_dt')
def local_dt_filter(dt):
    return _local(dt)
