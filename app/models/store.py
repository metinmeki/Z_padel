from datetime import datetime
from app import db


# ═══════════════════════════════════════════
# PRODUCT CATEGORY
# ═══════════════════════════════════════════
class Category(db.Model):
    __tablename__ = 'categories'

    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(80), unique=True, nullable=False)
    color      = db.Column(db.String(10), default='#1565C0')
    created_at = db.Column(db.DateTime,  default=datetime.utcnow)

    products = db.relationship('Product', backref='category', lazy=True)

    def __repr__(self):
        return f'<Category {self.name}>'


# ═══════════════════════════════════════════
# PRODUCT
# ═══════════════════════════════════════════
class Product(db.Model):
    __tablename__ = 'products'

    id              = db.Column(db.Integer, primary_key=True)
    category_id     = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    name            = db.Column(db.String(120), nullable=False)
    description     = db.Column(db.Text,        nullable=True)
    price           = db.Column(db.Float,       nullable=False, default=0)
    stock           = db.Column(db.Integer,     default=0)
    max_stock       = db.Column(db.Integer,     default=50)
    barcode         = db.Column(db.String(50),  unique=True, nullable=True)
    image           = db.Column(db.String(200), nullable=True)
    is_active       = db.Column(db.Boolean,     default=True)
    show_on_website = db.Column(db.Boolean,     default=False)   # ← NEW
    created_at      = db.Column(db.DateTime,    default=datetime.utcnow)

    order_items = db.relationship('OrderItem', backref='product', lazy=True)

    def __repr__(self):
        return f'<Product {self.name}>'


# ═══════════════════════════════════════════
# ORDER
# ═══════════════════════════════════════════
class Order(db.Model):
    __tablename__ = 'orders'

    id             = db.Column(db.Integer, primary_key=True)
    customer_name  = db.Column(db.String(100), nullable=True)
    customer_phone = db.Column(db.String(20),  nullable=True)
    total_price    = db.Column(db.Float,       default=0)
    status         = db.Column(db.String(20),  default='pending')
    # pending | processing | completed | cancelled
    notes          = db.Column(db.Text,        nullable=True)
    created_at     = db.Column(db.DateTime,    default=datetime.utcnow)
    updated_at     = db.Column(db.DateTime,    default=datetime.utcnow,
                               onupdate=datetime.utcnow)

    items = db.relationship('OrderItem', backref='order', lazy=True,
                            cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Order #{self.id}>'


# ═══════════════════════════════════════════
# ORDER ITEM
# ═══════════════════════════════════════════
class OrderItem(db.Model):
    __tablename__ = 'order_items'

    id         = db.Column(db.Integer, primary_key=True)
    order_id   = db.Column(db.Integer, db.ForeignKey('orders.id'),   nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    quantity   = db.Column(db.Integer, default=1)
    price      = db.Column(db.Float,   default=0)   # unit price at time of sale
    subtotal   = db.Column(db.Float,   default=0)

    def __repr__(self):
        return f'<OrderItem order#{self.order_id} product#{self.product_id}>'


# ═══════════════════════════════════════════
# EXPENSE CATEGORY
# ═══════════════════════════════════════════
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


# ═══════════════════════════════════════════
# EXPENSE
# ═══════════════════════════════════════════
class Expense(db.Model):
    __tablename__ = 'expenses'

    id          = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('expense_categories.id'), nullable=True)
    description = db.Column(db.String(200), nullable=False)
    amount      = db.Column(db.Float,       nullable=False, default=0)
    date        = db.Column(db.Date,        nullable=False, default=datetime.utcnow)
    notes       = db.Column(db.Text,        nullable=True)
    receipt     = db.Column(db.String(200), nullable=True)
    added_by    = db.Column(db.String(80),  nullable=True)
    created_at  = db.Column(db.DateTime,    default=datetime.utcnow)

    def __repr__(self):
        return f'<Expense {self.description} {self.amount}>'