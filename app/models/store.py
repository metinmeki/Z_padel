from app import db
from datetime import datetime


class Product(db.Model):
    __tablename__ = 'product'
    id               = db.Column(db.Integer, primary_key=True)
    name             = db.Column(db.String(120), nullable=False)
    description      = db.Column(db.Text)
    price            = db.Column(db.Float, nullable=False)
    image            = db.Column(db.String(200))
    stock            = db.Column(db.Integer, default=0)
    is_active        = db.Column(db.Boolean, default=True)
    show_on_website  = db.Column(db.Boolean, default=False)   # ← NEW
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    order_items = db.relationship('OrderItem', backref='product', lazy=True)

    def __repr__(self):
        return f'<Product {self.name}>'


class Order(db.Model):
    __tablename__ = 'order'
    id             = db.Column(db.Integer, primary_key=True)
    customer_name  = db.Column(db.String(120), nullable=False)
    customer_phone = db.Column(db.String(30), nullable=False)
    notes          = db.Column(db.Text)
    total_price    = db.Column(db.Float, nullable=False, default=0)
    status         = db.Column(db.String(30), default='pending')
    source         = db.Column(db.String(20), default='website')  # 'website' or 'pos'
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Order #{self.id} {self.status}>'


class OrderItem(db.Model):
    __tablename__ = 'order_item'
    id         = db.Column(db.Integer, primary_key=True)
    order_id   = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity   = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Float, nullable=False)

    @property
    def subtotal(self):
        return self.unit_price * self.quantity