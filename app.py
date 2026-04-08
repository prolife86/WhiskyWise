import os
import csv
import io
import json
from datetime import datetime
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, jsonify, send_file, session, abort)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                          login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image

app = Flask(__name__)

# Config
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
db_path = os.environ.get('DATABASE_PATH', 'data/db/whiskywise.db')
os.makedirs(os.path.dirname(db_path), exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', 'data/uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
FLAVOR_PROFILES = [
    'floral', 'fresh', 'fruity', 'malty', 'medicinal',
    'oily', 'peaty', 'smoky', 'spicy', 'sweet',
    'vanilla', 'vegetative', 'woody'
]

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# ── Models ──────────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, pw): self.password_hash = generate_password_hash(pw)
    def check_password(self, pw): return check_password_hash(self.password_hash, pw)


class Whisky(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    distillery = db.Column(db.String(200))
    region = db.Column(db.String(100))
    age = db.Column(db.String(20))
    abv = db.Column(db.Float)
    barcode = db.Column(db.String(100))

    # Collection status
    status = db.Column(db.String(20), default='stashed')  # open, stashed, finished
    retired = db.Column(db.Boolean, default=False)
    price = db.Column(db.Float)
    store = db.Column(db.String(200))

    # Tasting notes
    notes = db.Column(db.Text)
    nose = db.Column(db.Text)
    palate = db.Column(db.Text)
    finish = db.Column(db.Text)
    flavor_profile = db.Column(db.String(50))
    score = db.Column(db.Float)

    # Photos (stored as comma-separated filenames)
    photo_front = db.Column(db.String(300))
    photo_back = db.Column(db.String(300))
    photo_cask = db.Column(db.String(300))
    photo_barcode = db.Column(db.String(300))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    wishlist = db.Column(db.Boolean, default=False)
    wishlist_notes = db.Column(db.Text)

    user = db.relationship('User', backref='whiskies')


@login_manager.user_loader
def load_user(uid):
    return User.query.get(int(uid))


# ── Helpers ──────────────────────────────────────────────────────────────────

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_photo(file, whisky_id, slot):
    if not file or file.filename == '':
        return None
    if not allowed_file(file.filename):
        return None
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = secure_filename(f"w{whisky_id}_{slot}_{int(datetime.utcnow().timestamp())}.{ext}")
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    img = Image.open(file)
    img.thumbnail((1200, 1200))
    img.save(path, optimize=True, quality=85)
    return filename


def first_run_check():
    with app.app_context():
        db.create_all()
        if not User.query.first():
            u = User(username='admin')
            u.set_password('whiskywise')
            db.session.add(u)
            db.session.commit()
            print("Created default admin user (password: whiskywise)")


# ── Auth ─────────────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        u = User.query.filter_by(username=request.form['username']).first()
        if u and u.check_password(request.form['password']):
            login_user(u, remember=True)
            return redirect(request.args.get('next') or url_for('index'))
        flash('Invalid username or password', 'error')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        if not current_user.check_password(request.form['current']):
            flash('Current password is incorrect', 'error')
        elif request.form['new'] != request.form['confirm']:
            flash('New passwords do not match', 'error')
        else:
            current_user.set_password(request.form['new'])
            db.session.commit()
            flash('Password changed successfully', 'success')
            return redirect(url_for('index'))
    return render_template('change_password.html')


# ── Main pages ───────────────────────────────────────────────────────────────

@app.route('/')
@login_required
def index():
    top10 = (Whisky.query
             .filter_by(user_id=current_user.id, wishlist=False)
             .filter(Whisky.score.isnot(None))
             .order_by(Whisky.score.desc())
             .limit(10).all())
    total = Whisky.query.filter_by(user_id=current_user.id, wishlist=False).count()
    open_count = Whisky.query.filter_by(user_id=current_user.id, status='open', wishlist=False).count()
    stashed = Whisky.query.filter_by(user_id=current_user.id, status='stashed', wishlist=False).count()
    wishlist_count = Whisky.query.filter_by(user_id=current_user.id, wishlist=True).count()
    return render_template('index.html', top10=top10, total=total,
                           open_count=open_count, stashed=stashed,
                           wishlist_count=wishlist_count,
                           flavor_profiles=FLAVOR_PROFILES)


@app.route('/collection')
@login_required
def collection():
    q = request.args.get('q', '').strip()
    flavor = request.args.get('flavor', '')
    min_score = request.args.get('min_score', '')
    max_price = request.args.get('max_price', '')
    status_filter = request.args.get('status', '')

    query = Whisky.query.filter_by(user_id=current_user.id, wishlist=False)

    if q:
        like = f'%{q}%'
        query = query.filter(
            db.or_(Whisky.name.ilike(like), Whisky.distillery.ilike(like),
                   Whisky.barcode.ilike(like), Whisky.region.ilike(like))
        )
    if flavor:
        query = query.filter(Whisky.flavor_profile == flavor)
    if min_score:
        try: query = query.filter(Whisky.score >= float(min_score))
        except: pass
    if max_price:
        try: query = query.filter(Whisky.price <= float(max_price))
        except: pass
    if status_filter:
        query = query.filter(Whisky.status == status_filter)

    whiskies = query.order_by(Whisky.score.desc().nullslast(), Whisky.name).all()
    return render_template('collection.html', whiskies=whiskies,
                           flavor_profiles=FLAVOR_PROFILES,
                           filters=dict(q=q, flavor=flavor, min_score=min_score,
                                        max_price=max_price, status=status_filter))


@app.route('/wishlist')
@login_required
def wishlist():
    items = Whisky.query.filter_by(user_id=current_user.id, wishlist=True)\
                        .order_by(Whisky.created_at.desc()).all()
    return render_template('wishlist.html', items=items)


# ── Whisky CRUD ──────────────────────────────────────────────────────────────

@app.route('/whisky/new', methods=['GET', 'POST'])
@login_required
def new_whisky():
    if request.method == 'POST':
        w = Whisky(user_id=current_user.id)
        _fill_whisky(w, request.form)
        db.session.add(w)
        db.session.flush()
        _handle_photos(w, request.files)
        db.session.commit()
        flash('Whisky added!', 'success')
        return redirect(url_for('whisky_detail', wid=w.id))
    return render_template('whisky_form.html', whisky=None, flavor_profiles=FLAVOR_PROFILES, is_wishlist=False)


@app.route('/whisky/<int:wid>')
@login_required
def whisky_detail(wid):
    w = Whisky.query.filter_by(id=wid, user_id=current_user.id).first_or_404()
    return render_template('whisky_detail.html', w=w, flavor_profiles=FLAVOR_PROFILES)


@app.route('/whisky/<int:wid>/edit', methods=['GET', 'POST'])
@login_required
def edit_whisky(wid):
    w = Whisky.query.filter_by(id=wid, user_id=current_user.id).first_or_404()
    if request.method == 'POST':
        _fill_whisky(w, request.form)
        _handle_photos(w, request.files)
        w.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Updated!', 'success')
        return redirect(url_for('whisky_detail', wid=w.id))
    return render_template('whisky_form.html', whisky=w, flavor_profiles=FLAVOR_PROFILES,
                           is_wishlist=w.wishlist)


@app.route('/whisky/<int:wid>/delete', methods=['POST'])
@login_required
def delete_whisky(wid):
    w = Whisky.query.filter_by(id=wid, user_id=current_user.id).first_or_404()
    db.session.delete(w)
    db.session.commit()
    flash('Deleted', 'info')
    return redirect(url_for('collection'))


@app.route('/whisky/new-wishlist', methods=['GET', 'POST'])
@login_required
def new_wishlist_item():
    if request.method == 'POST':
        w = Whisky(user_id=current_user.id, wishlist=True)
        w.name = request.form.get('name', '')
        w.distillery = request.form.get('distillery', '')
        w.region = request.form.get('region', '')
        w.price = _float_or_none(request.form.get('price'))
        w.store = request.form.get('store', '')
        w.wishlist_notes = request.form.get('wishlist_notes', '')
        w.barcode = request.form.get('barcode', '')
        db.session.add(w)
        db.session.commit()
        flash('Added to wishlist!', 'success')
        return redirect(url_for('wishlist'))
    return render_template('wishlist_form.html')


def _fill_whisky(w, form):
    w.name = form.get('name', '')
    w.distillery = form.get('distillery', '')
    w.region = form.get('region', '')
    w.age = form.get('age', '')
    w.abv = _float_or_none(form.get('abv'))
    w.barcode = form.get('barcode', '')
    w.status = form.get('status', 'stashed')
    w.retired = form.get('retired') == 'on'
    w.price = _float_or_none(form.get('price'))
    w.store = form.get('store', '')
    w.notes = form.get('notes', '')
    w.nose = form.get('nose', '')
    w.palate = form.get('palate', '')
    w.finish = form.get('finish', '')
    w.flavor_profile = form.get('flavor_profile', '')
    w.score = _float_or_none(form.get('score'))
    w.wishlist = form.get('wishlist') == 'on'
    w.wishlist_notes = form.get('wishlist_notes', '')


def _handle_photos(w, files):
    for slot in ('front', 'back', 'cask', 'barcode'):
        f = files.get(f'photo_{slot}')
        if f and f.filename:
            saved = save_photo(f, w.id, slot)
            if saved:
                setattr(w, f'photo_{slot}', saved)


def _float_or_none(val):
    try: return float(val) if val else None
    except: return None


# ── API helpers ───────────────────────────────────────────────────────────────

@app.route('/api/barcode-lookup')
@login_required
def barcode_lookup():
    code = request.args.get('code', '')
    existing = Whisky.query.filter_by(user_id=current_user.id, barcode=code).first()
    if existing:
        return jsonify({'found': True, 'id': existing.id, 'name': existing.name})
    return jsonify({'found': False})


@app.route('/api/photo/<filename>')
@login_required
def serve_photo(filename):
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(path):
        abort(404)
    return send_file(path)


# ── Export ────────────────────────────────────────────────────────────────────

@app.route('/export/csv')
@login_required
def export_csv():
    whiskies = Whisky.query.filter_by(user_id=current_user.id, wishlist=False).all()
    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow(['Name','Distillery','Region','Age','ABV','Barcode','Status','Retired',
                     'Price','Store','Flavor Profile','Score','Nose','Palate','Finish','Notes',
                     'Added'])
    for w in whiskies:
        writer.writerow([w.name, w.distillery, w.region, w.age, w.abv, w.barcode,
                         w.status, w.retired, w.price, w.store,
                         w.flavor_profile, w.score, w.nose, w.palate, w.finish, w.notes,
                         w.created_at.strftime('%Y-%m-%d')])
    output = io.BytesIO()
    output.write(si.getvalue().encode('utf-8'))
    output.seek(0)
    return send_file(output, mimetype='text/csv',
                     download_name='whiskywise_export.csv', as_attachment=True)


if __name__ == '__main__':
    first_run_check()
    app.run(debug=False, host='0.0.0.0', port=5000)

# Ensure DB is created on startup
first_run_check()
