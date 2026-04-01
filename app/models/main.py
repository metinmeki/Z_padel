from app import db, login_manager
from flask_login import UserMixin
from datetime import datetime


@login_manager.user_loader
def load_user(user_id):
    return Admin.query.get(int(user_id))


class Admin(UserMixin, db.Model):
    __tablename__ = 'admins'
    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(50), unique=True, nullable=False)
    password   = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Court(db.Model):
    __tablename__ = 'courts'
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(100), nullable=False)
    description   = db.Column(db.Text)
    price_per_hour = db.Column(db.Float, nullable=False)
    image         = db.Column(db.String(200))
    is_active     = db.Column(db.Boolean, default=True)
    bookings      = db.relationship('Booking', backref='court', lazy=True)


class Booking(db.Model):
    __tablename__ = 'bookings'
    id             = db.Column(db.Integer, primary_key=True)
    customer_name  = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    court_id       = db.Column(db.Integer, db.ForeignKey('courts.id'), nullable=False)
    date           = db.Column(db.Date, nullable=False)
    start_time     = db.Column(db.Time, nullable=False)
    end_time       = db.Column(db.Time, nullable=False)
    total_price    = db.Column(db.Float, nullable=False)
    status         = db.Column(db.String(20), default='pending')
    notes          = db.Column(db.Text)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)