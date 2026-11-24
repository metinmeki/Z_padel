from datetime import datetime
from app import db


class Category(db.Model):
    __tablename__ = 'categories'

    id             = db.Column(db.Integer, primary_key=True)
    name           = db.Column(db.String(80), unique=True, nullable=False)
    color          = db.Column(db.String(10), default='#1565C0')
    show_in_store  = db.Column(db.Boolean, default=True)
    show_on_menu   = db.Column(db.Boolean, default=False)   # café menu at menu.z-padel.com
    name_ar        = db.Column(db.String(80), nullable=True)
    name_ku        = db.Column(db.String(80), nullable=True)
    created_at     = db.Column(db.DateTime,  default=datetime.utcnow)

    products = db.relationship('Product', backref='category', lazy=True)

    def __repr__(self):
        return f'<Category {self.name}>'


class Product(db.Model):
    __tablename__ = 'products'

    id              = db.Column(db.Integer, primary_key=True)
    category_id     = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    name            = db.Column(db.String(120), nullable=False)
    description     = db.Column(db.Text,        nullable=True)
    description_ar  = db.Column(db.Text,        nullable=True)
    description_ku  = db.Column(db.Text,        nullable=True)
    price           = db.Column(db.Float,       nullable=False, default=0)
    stock           = db.Column(db.Integer,     default=0)
    max_stock       = db.Column(db.Integer,     default=50)
    barcode         = db.Column(db.String(50),  unique=True, nullable=True)
    image           = db.Column(db.String(200), nullable=True)
    is_active       = db.Column(db.Boolean,     default=True)
    show_on_website = db.Column(db.Boolean,     default=False)
    show_on_menu    = db.Column(db.Boolean,     default=True)    # shown when its category is on the menu
    name_ar         = db.Column(db.String(120), nullable=True)
    name_ku         = db.Column(db.String(120), nullable=True)
    created_at      = db.Column(db.DateTime,    default=datetime.utcnow)

    order_items = db.relationship('OrderItem', backref='product', lazy=True)

    def __repr__(self):
        return f'<Product {self.name}>'


class Order(db.Model):
    __tablename__ = 'orders'

    id             = db.Column(db.Integer, primary_key=True)
    customer_name  = db.Column(db.String(100), nullable=True)
    customer_phone = db.Column(db.String(20),  nullable=True)
    total_price    = db.Column(db.Float,       default=0)
    status         = db.Column(db.String(20),  default='pending')
    notes          = db.Column(db.Text,        nullable=True)
    created_at     = db.Column(db.DateTime,    default=datetime.utcnow)
    updated_at     = db.Column(db.DateTime,    default=datetime.utcnow,
                               onupdate=datetime.utcnow)

    items = db.relationship('OrderItem', backref='order', lazy=True,
                            cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Order #{self.id}>'


class OrderItem(db.Model):
    __tablename__ = 'order_items'

    id           = db.Column(db.Integer, primary_key=True)
    order_id     = db.Column(db.Integer, db.ForeignKey('orders.id'),   nullable=False)
    product_id   = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    product_name = db.Column(db.String(120), nullable=True)   # for virtual/activity items
    quantity     = db.Column(db.Integer, default=1)
    price        = db.Column(db.Float,   default=0)
    subtotal     = db.Column(db.Float,   default=0)

    def __repr__(self):
        return f'<OrderItem order#{self.order_id} product#{self.product_id}>'


# ═══════════════════════════════════════════
# MENU ORDERS  (sent by customers from menu.z-padel.com, handled by the barista)
# ═══════════════════════════════════════════
class MenuOrder(db.Model):
    __tablename__ = 'menu_orders'

    id             = db.Column(db.Integer, primary_key=True)
    code           = db.Column(db.String(24), unique=True, nullable=False, index=True)   # secret, for the customer's status page
    place_type     = db.Column(db.String(10), nullable=False)       # court / table / counter
    place_id       = db.Column(db.Integer, nullable=True)            # Court.id or ActivityTable.id
    place_label    = db.Column(db.String(80), default='')            # e.g. "Court 1", kept as it was when ordered
    customer_name  = db.Column(db.String(80), nullable=True)
    note           = db.Column(db.String(300), nullable=True)
    total          = db.Column(db.Float, default=0)
    # pending -> accepted -> (paid)   or   pending -> rejected   or   accepted -> cancelled (counter, never paid)
    status         = db.Column(db.String(12), default='pending', index=True)
    billed_to      = db.Column(db.String(20), nullable=True)         # court_session / activity_session / counter
    session_id     = db.Column(db.Integer, nullable=True)            # the court/activity session the items went on
    order_id       = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=True)   # POS sale once a counter order is paid
    reject_reason  = db.Column(db.String(200), nullable=True)
    handled_by     = db.Column(db.String(80), nullable=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    decided_at     = db.Column(db.DateTime, nullable=True)

    items = db.relationship('MenuOrderItem', backref='menu_order', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<MenuOrder #{self.id} {self.place_label} {self.status}>'


class MenuOrderItem(db.Model):
    __tablename__ = 'menu_order_items'

    id            = db.Column(db.Integer, primary_key=True)
    menu_order_id = db.Column(db.Integer, db.ForeignKey('menu_orders.id'), nullable=False)
    product_id    = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    product_name  = db.Column(db.String(120), nullable=False)
    price         = db.Column(db.Float, default=0)
    quantity      = db.Column(db.Integer, default=1)
    subtotal      = db.Column(db.Float, default=0)


class ExpenseCategory(db.Model):
    __tablename__ = 'expense_categories'

    id    = db.Column(db.Integer, primary_key=True)
    name  = db.Column(db.String(80), unique=True, nullable=False)
    color = db.Column(db.String(10), default='#E53935')

    expenses = db.relationship('Expense', backref='category', lazy=True)

    @property
    def total(self):
        return sum(e.amount or 0 for e in self.expenses)

    def __repr__(self):
        return f'<ExpenseCategory {self.name}>'


class Expense(db.Model):
    __tablename__ = 'expenses'

    id           = db.Column(db.Integer, primary_key=True)
    category_id  = db.Column(db.Integer, db.ForeignKey('expense_categories.id'), nullable=True)
    description  = db.Column(db.String(200), nullable=False)
    amount       = db.Column(db.Float,       nullable=False, default=0)
    date         = db.Column(db.Date,        nullable=False, default=datetime.utcnow)
    salary_month = db.Column(db.Date,        nullable=True)   # e.g. 2026-08-01 = "for August"
    notes        = db.Column(db.Text,        nullable=True)
    receipt      = db.Column(db.String(200), nullable=True)
    added_by     = db.Column(db.String(80),  nullable=True)
    created_at   = db.Column(db.DateTime,    default=datetime.utcnow)

    def __repr__(self):
        return f'<Expense {self.description} {self.amount}>'


class StaffConsumption(db.Model):
    __tablename__ = 'staff_consumption'

    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=True)
    username     = db.Column(db.String(80),  nullable=False)
    product_id   = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    product_name = db.Column(db.String(120), nullable=False)
    quantity     = db.Column(db.Integer, default=1)
    unit_price   = db.Column(db.Float,   default=0)
    subtotal     = db.Column(db.Float,   default=0)
    consumed_at  = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    note         = db.Column(db.String(200), nullable=True)

    def __repr__(self):
        return f'<StaffConsumption {self.username} {self.product_name}>'