from datetime import datetime, date, time
from flask_login import UserMixin
from app import db, login_manager


# ── User loader ──
@login_manager.user_loader
def load_user(user_id):
    return Admin.query.get(int(user_id))


# ═══════════════════════════════════════════
# ADMIN (system users)
# ═══════════════════════════════════════════
class Admin(UserMixin, db.Model):
    __tablename__ = 'admins'

    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(80),  unique=True, nullable=False)
    password   = db.Column(db.String(256), nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=True)
    role       = db.Column(db.String(20),  default='staff')
    is_active  = db.Column(db.Boolean,     default=True)
    last_login = db.Column(db.DateTime,    nullable=True)
    created_at = db.Column(db.DateTime,    default=datetime.utcnow)

    _permissions = db.Column('permissions', db.Text, default='{}')

    @property
    def permissions(self):
        import json
        try:
            return json.loads(self._permissions or '{}')
        except Exception:
            return {}

    @permissions.setter
    def permissions(self, val):
        import json
        self._permissions = json.dumps(val)

    def has_perm(self, perm: str) -> bool:
        if self.role in ('superadmin', 'admin'):
            return True
        return self.permissions.get(perm, False)

    def __repr__(self):
        return f'<Admin {self.username}>'


# ═══════════════════════════════════════════
# COURT
# ═══════════════════════════════════════════
class Court(db.Model):
    __tablename__ = 'courts'

    id             = db.Column(db.Integer, primary_key=True)
    name           = db.Column(db.String(100), nullable=False)
    description    = db.Column(db.Text,        nullable=True)
    price_per_hour = db.Column(db.Float,       default=25000)
    color          = db.Column(db.String(10),  default='#1565C0')
    capacity       = db.Column(db.Integer,     nullable=True)
    surface_type   = db.Column(db.String(50),  nullable=True)
    is_active      = db.Column(db.Boolean,     default=True)
    created_at     = db.Column(db.DateTime,    default=datetime.utcnow)
    image          = db.Column(db.String(200), nullable=True)

    # lazy='select' prevents loading ALL bookings when court is accessed
    bookings = db.relationship('Booking', backref='court',
                               lazy='select',
                               cascade='all, delete-orphan')

    @property
    def total_bookings(self):
        """Single COUNT query — no full row load."""
        from sqlalchemy import func
        return db.session.query(func.count(Booking.id)) \
                   .filter(Booking.court_id == self.id).scalar() or 0

    @property
    def today_booked_slots(self):
        """Single targeted query — fixes N+1 problem."""
        from sqlalchemy import and_
        slots = db.session.query(Booking.start_time).filter(
            and_(
                Booking.court_id == self.id,
                Booking.booking_date == date.today(),
                Booking.status != 'cancelled'
            )
        ).all()
        return [s.start_time.strftime('%H') for s in slots if s.start_time]

    def __repr__(self):
        return f'<Court {self.name}>'


# ═══════════════════════════════════════════
# BOOKING
# ═══════════════════════════════════════════
class Booking(db.Model):
    __tablename__ = 'bookings'

    id             = db.Column(db.Integer, primary_key=True)
    court_id       = db.Column(db.Integer, db.ForeignKey('courts.id'), nullable=False)
    customer_name  = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20),  nullable=False)
    booking_date   = db.Column(db.Date,        nullable=False)
    start_time     = db.Column(db.Time,        nullable=False)
    end_time       = db.Column(db.Time,        nullable=False)
    total_price    = db.Column(db.Float,       default=0)
    status         = db.Column(db.String(20),  default='pending')
    # pending | confirmed | cancelled
    notes          = db.Column(db.Text,        nullable=True)
    created_at     = db.Column(db.DateTime,    default=datetime.utcnow)
    updated_at     = db.Column(db.DateTime,    default=datetime.utcnow,
                               onupdate=datetime.utcnow)

    cancel_request = db.relationship('CancelRequest', backref='booking',
                                     uselist=False, cascade='all, delete-orphan')

    @property
    def waiting_minutes(self):
        if self.status != 'pending':
            return 0
        delta = datetime.utcnow() - self.created_at
        return int(delta.total_seconds() / 60)

    @property
    def is_discount_slot(self):
        if self.start_time:
            return 12 <= self.start_time.hour < 16
        return False

    def calc_price(self, base_price: float, discount_pct: int = 25) -> float:
        if not self.start_time or not self.end_time:
            return 0
        start_m = self.start_time.hour * 60 + self.start_time.minute
        end_m   = self.end_time.hour   * 60 + self.end_time.minute
        hours   = (end_m - start_m) / 60
        rate    = base_price * (1 - discount_pct / 100) if self.is_discount_slot else base_price
        return round(hours * rate)

    def __repr__(self):
        return f'<Booking #{self.id} {self.customer_name}>'


# ═══════════════════════════════════════════
# CANCEL REQUEST
# ═══════════════════════════════════════════
class CancelRequest(db.Model):
    __tablename__ = 'cancel_requests'

    id         = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False)
    reason     = db.Column(db.String(200), nullable=True)
    notes      = db.Column(db.Text,        nullable=True)
    status     = db.Column(db.String(20),  default='pending')
    created_at = db.Column(db.DateTime,    default=datetime.utcnow)

    def __repr__(self):
        return f'<CancelRequest booking#{self.booking_id}>'


# ═══════════════════════════════════════════
# COACH
# ═══════════════════════════════════════════
class Coach(db.Model):
    __tablename__ = 'coaches'

    id             = db.Column(db.Integer, primary_key=True)
    name           = db.Column(db.String(100), nullable=False)
    phone          = db.Column(db.String(20),  nullable=True)
    specialty      = db.Column(db.String(100), nullable=True)
    price_per_hour = db.Column(db.Float,       default=0)
    is_active      = db.Column(db.Boolean,     default=True)
    bio            = db.Column(db.Text,        nullable=True)
    image          = db.Column(db.String(255), nullable=True)  # ✅ ADD THIS
    status         = db.Column(db.String(50),  default='available')  # ✅ ADD THIS
    created_at     = db.Column(db.DateTime,    default=datetime.utcnow)

# ═══════════════════════════════════════════
# TRAINING REQUEST
# ═══════════════════════════════════════════
class TrainingRequest(db.Model):
    __tablename__ = 'training_requests'

    id             = db.Column(db.Integer, primary_key=True)
    coach_id       = db.Column(db.Integer, db.ForeignKey('coaches.id'), nullable=False)
    customer_name  = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20),  nullable=False)
    preferred_date = db.Column(db.Date,        nullable=True)
    preferred_time = db.Column(db.Time,        nullable=True)
    status         = db.Column(db.String(20),  default='pending')
    notes          = db.Column(db.Text,        nullable=True)
    created_at     = db.Column(db.DateTime,    default=datetime.utcnow)

    def __repr__(self):
        return f'<TrainingRequest #{self.id}>'


# ═══════════════════════════════════════════
# SYSTEM SETTINGS
# ═══════════════════════════════════════════
class SystemSetting(db.Model):
    __tablename__ = 'system_settings'

    id    = db.Column(db.Integer, primary_key=True)
    key   = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)

    @staticmethod
    def get(key, default=None):
        row = SystemSetting.query.filter_by(key=key).first()
        return row.value if row else default

    @staticmethod
    def set(key, value):
        row = SystemSetting.query.filter_by(key=key).first()
        if row:
            row.value = str(value)
        else:
            db.session.add(SystemSetting(key=key, value=str(value)))
        db.session.commit()

    def __repr__(self):
        return f'<Setting {self.key}={self.value}>'



class PushSubscription(db.Model):
    __tablename__ = 'push_subscriptions'
    id        = db.Column(db.Integer, primary_key=True)
    endpoint  = db.Column(db.Text, unique=True, nullable=False)
    p256dh    = db.Column(db.String(255), nullable=False)
    auth      = db.Column(db.String(255), nullable=False)
    created   = db.Column(db.DateTime, default=datetime.utcnow)

# ═══════════════════════════════════════════
# COURT SESSION (live walk-in play timer — POS)
# ═══════════════════════════════════════════
class CourtSession(db.Model):
    __tablename__ = 'court_sessions'

    id             = db.Column(db.Integer, primary_key=True)
    court_id       = db.Column(db.Integer, db.ForeignKey('courts.id'), nullable=False)
    start_time     = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    end_time       = db.Column(db.DateTime, nullable=True)
    status         = db.Column(db.String(20), default='active')
    total_price    = db.Column(db.Float, default=0)
    payment_method = db.Column(db.String(20), nullable=True)
    customer_name  = db.Column(db.String(100), nullable=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    court = db.relationship('Court', backref='sessions')

    @property
    def elapsed_minutes(self):
        end = self.end_time or datetime.utcnow()
        delta = end - self.start_time
        return max(0, int(delta.total_seconds() // 60))

    def calc_price(self):
        hours = self.elapsed_minutes / 60
        rate = self.court.price_per_hour if self.court else 40000
        return round(hours * rate)

    @property
    def items_total(self):
        return sum(i.subtotal for i in self.items) if self.items else 0

    @property
    def time_amount(self):
        if self.status == 'active' and not self.end_time:
            return self.calc_price()
        return self.total_price or 0

    @property
    def grand_total(self):
        return round(self.time_amount + self.items_total)

    def __repr__(self):
        return f'<CourtSession court#{self.court_id} status={self.status}>'


# ═══════════════════════════════════════════
# COURT SESSION ITEM (products added during a live session)
# ═══════════════════════════════════════════
class CourtSessionItem(db.Model):
    __tablename__ = 'court_session_items'

    id           = db.Column(db.Integer, primary_key=True)
    session_id   = db.Column(db.Integer, db.ForeignKey('court_sessions.id'), nullable=False)
    product_id   = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    product_name = db.Column(db.String(120), nullable=False)
    quantity     = db.Column(db.Integer, default=1)
    price        = db.Column(db.Float, default=0)
    subtotal     = db.Column(db.Float, default=0)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    session = db.relationship('CourtSession', backref=db.backref('items', lazy=True, cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<CourtSessionItem session#{self.session_id} {self.product_name}>'
