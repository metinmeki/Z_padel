from flask import Blueprint, render_template
from app.models import Court

main = Blueprint('main', __name__)

@main.route('/')
def index():
    courts = Court.query.filter_by(is_active=True).all()
    return render_template('index.html', courts=courts)
