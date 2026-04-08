import os
import csv
import io
from datetime import datetime

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, jsonify, send_file, abort)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                          login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image

app = Flask(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-me')

db_path = os.environ.get('DATABASE_PATH', 'data/db/whiskywise.db')
_db_dir = os.path.dirname(db_path)
if _db_dir:
    os.makedirs(_db_dir, exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

upload_folder = os.environ.get('UPLOAD_FOLDER', 'data/uploads')
os.makedirs(upload_folder, exist_ok=True)
app.config['UPLOAD_FOLDER'] = upload_folder
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
FLAVOR_PROFILES = [
    'floral', 'fresh', 'fruity', 'malty', 'medicinal',
    'oily', 'peaty', 'smoky', 'spicy', 'sweet',
    'vanilla', 'vegetative', 'woody',
]

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# ── Models ────────────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)


class Whisky(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name         = db.Column(db.String(200), nullable=False)
    distillery   = db.Column(db.String(200))
    region       = db.Column(db.String(100))
    age          = db.Column(db.String(20))
    abv          = db.Column(db.Float)
    barcode      = db.Column(db.String(100))

    # Collection
    status   = db.Column(db.String(20), default='stashed')  # open | stashed | finished
    retired  = db.Column(db.Boolean, default=False)
    price    = db.Column(db.Float)
    store    = db.Column(db.String(200))

    # Tasting
    notes         = db.Column(db.Text)
    nose          = db.Column(db.Text)
    palate        = db.Column(db.Text)
    finish        = db.Column(db.Text)
    flavor_profile = db.Column(db.String(50))
    score         = db.Column(db.Float)   # 0.0–10.0, nullable = unscored

    # Photos
    photo_front   = db.Column(db.String(300))
    photo_back    = db.Column(db.String(300))
    photo_cask    = db.Column(db.String(300))
    photo_barcode = db.Column(db.String(300))

    # Wishlist
    wishlist       = db.Column(db.Boolean, default=False)
    wishlist_notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref='whiskies')


@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, int(uid))


# ── Helpers ───────────────────────────────────────────────────────────────────

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_photo(file, whisky_id, slot):
    """Resize and persist an uploaded photo; returns stored filename or None."""
    if not file or not file.filename:
        return None
    if not allowed_file(file.filename):
        return None
    ext = file.filename.rsplit('.', 1)[1].lower()
    save_ext = ext if ext in ('png', 'webp') else 'jpg'
    filename = secure_filename(
        f"w{whisky_id}_{slot}_{int(datetime.utcnow().timestamp())}.{save_ext}"
    )
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    try:
        img = Image.open(file)
        if save_ext == 'jpg' and img.mode != 'RGB':
            img = img.convert('RGB')
        img.thumbnail((1200, 1200), Image.LANCZOS)
        save_kwargs = {'optimize': True}
        if save_ext == 'jpg':
            save_kwargs['quality'] = 85
        img.save(path, **save_kwargs)
    except Exception as exc:
        app.logger.error("Photo save failed: %s", exc)
        return None
    return filename


def _float_or_none(val):
    try:
        return float(val) if val not in (None, '') else None
    except (ValueError, TypeError):
        return None


def _fill_whisky(w, form):
    """Populate whisky fields from a form dict. Does NOT touch w.wishlist."""
    w.name          = form.get('name', '').strip()
    w.distillery    = form.get('distillery', '').strip()
    w.region        = form.get('region', '').strip()
    w.age           = form.get('age', '').strip()
    w.abv           = _float_or_none(form.get('abv'))
    w.barcode       = form.get('barcode', '').strip()
    w.status        = form.get('status', 'stashed')
    w.retired       = form.get('retired') == 'on'
    w.price         = _float_or_none(form.get('price'))
    w.store         = form.get('store', '').strip()
    w.notes         = form.get('notes', '').strip()
    w.nose          = form.get('nose', '').strip()
    w.palate        = form.get('palate', '').strip()
    w.finish        = form.get('finish', '').strip()
    w.flavor_profile = form.get('flavor_profile', '').strip()
    w.score         = _float_or_none(form.get('score'))
    w.wishlist_notes = form.get('wishlist_notes', '').strip()


def _handle_photos(w, files):
    for slot in ('front', 'back', 'cask', 'barcode'):
        f = files.get(f'photo_{slot}')
        if f and f.filename:
            saved = save_photo(f, w.id, slot)
            if saved:
                setattr(w, f'photo_{slot}', saved)


def _init_db():
    """Create tables and default admin user on first boot."""
    with app.app_context():
        db.create_all()
        if not User.query.first():
            admin = User(username='admin')
            admin.set_password('whiskywise')
            db.session.add(admin)
            db.session.commit()
            print("[WhiskyWise] Default admin created — please change the password!")


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username', '')).first()
        if user and user.check_password(request.form.get('password', '')):
            login_user(user, remember=True)
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
        if not current_user.check_password(request.form.get('current', '')):
            flash('Current password is incorrect', 'error')
        elif request.form.get('new') != request.form.get('confirm'):
            flash('New passwords do not match', 'error')
        elif len(request.form.get('new', '')) < 6:
            flash('Password must be at least 6 characters', 'error')
        else:
            current_user.set_password(request.form['new'])
            db.session.commit()
            flash('Password changed successfully', 'success')
            return redirect(url_for('index'))
    return render_template('change_password.html')


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.route('/')
@login_required
def index():
    top10 = (Whisky.query
             .filter_by(user_id=current_user.id, wishlist=False)
             .filter(Whisky.score.isnot(None))
             .order_by(Whisky.score.desc())
             .limit(10).all())
    total          = Whisky.query.filter_by(user_id=current_user.id, wishlist=False).count()
    open_count     = Whisky.query.filter_by(user_id=current_user.id, status='open',    wishlist=False).count()
    stashed_count  = Whisky.query.filter_by(user_id=current_user.id, status='stashed', wishlist=False).count()
    wishlist_count = Whisky.query.filter_by(user_id=current_user.id, wishlist=True).count()
    return render_template('index.html',
                           top10=top10, total=total,
                           open_count=open_count, stashed=stashed_count,
                           wishlist_count=wishlist_count)


@app.route('/collection')
@login_required
def collection():
    q             = request.args.get('q', '').strip()
    flavor        = request.args.get('flavor', '')
    min_score     = request.args.get('min_score', '')
    max_price     = request.args.get('max_price', '')
    status_filter = request.args.get('status', '')

    query = Whisky.query.filter_by(user_id=current_user.id, wishlist=False)

    if q:
        like = f'%{q}%'
        query = query.filter(db.or_(
            Whisky.name.ilike(like), Whisky.distillery.ilike(like),
            Whisky.barcode.ilike(like), Whisky.region.ilike(like),
        ))
    if flavor:
        query = query.filter(Whisky.flavor_profile == flavor)
    if min_score:
        v = _float_or_none(min_score)
        if v is not None:
            query = query.filter(Whisky.score >= v)
    if max_price:
        v = _float_or_none(max_price)
        if v is not None:
            query = query.filter(Whisky.price <= v)
    if status_filter:
        query = query.filter(Whisky.status == status_filter)

    whiskies = query.order_by(Whisky.score.desc().nullslast(), Whisky.name).all()
    return render_template('collection.html',
                           whiskies=whiskies,
                           flavor_profiles=FLAVOR_PROFILES,
                           filters=dict(q=q, flavor=flavor, min_score=min_score,
                                        max_price=max_price, status=status_filter))


@app.route('/wishlist')
@login_required
def wishlist():
    items = (Whisky.query
             .filter_by(user_id=current_user.id, wishlist=True)
             .order_by(Whisky.created_at.desc()).all())
    return render_template('wishlist.html', items=items)


# ── Whisky CRUD ───────────────────────────────────────────────────────────────

@app.route('/whisky/new', methods=['GET', 'POST'])
@login_required
def new_whisky():
    if request.method == 'POST':
        w = Whisky(user_id=current_user.id, wishlist=False)
        _fill_whisky(w, request.form)
        db.session.add(w)
        db.session.flush()          # get w.id before saving photos
        _handle_photos(w, request.files)
        db.session.commit()
        flash('Whisky added!', 'success')
        return redirect(url_for('whisky_detail', wid=w.id))
    return render_template('whisky_form.html', whisky=None, flavor_profiles=FLAVOR_PROFILES)


@app.route('/whisky/<int:wid>')
@login_required
def whisky_detail(wid):
    w = Whisky.query.filter_by(id=wid, user_id=current_user.id).first_or_404()
    return render_template('whisky_detail.html', w=w)


@app.route('/whisky/<int:wid>/edit', methods=['GET', 'POST'])
@login_required
def edit_whisky(wid):
    w = Whisky.query.filter_by(id=wid, user_id=current_user.id).first_or_404()
    if request.method == 'POST':
        _fill_whisky(w, request.form)
        _handle_photos(w, request.files)
        w.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Saved!', 'success')
        return redirect(url_for('whisky_detail', wid=w.id))
    return render_template('whisky_form.html', whisky=w, flavor_profiles=FLAVOR_PROFILES)


@app.route('/whisky/<int:wid>/delete', methods=['POST'])
@login_required
def delete_whisky(wid):
    w = Whisky.query.filter_by(id=wid, user_id=current_user.id).first_or_404()
    was_wishlist = w.wishlist
    db.session.delete(w)
    db.session.commit()
    flash('Deleted.', 'info')
    return redirect(url_for('wishlist') if was_wishlist else url_for('collection'))


@app.route('/whisky/new-wishlist', methods=['GET', 'POST'])
@login_required
def new_wishlist_item():
    if request.method == 'POST':
        w = Whisky(user_id=current_user.id, wishlist=True)
        w.name           = request.form.get('name', '').strip()
        w.distillery     = request.form.get('distillery', '').strip()
        w.region         = request.form.get('region', '').strip()
        w.price          = _float_or_none(request.form.get('price'))
        w.store          = request.form.get('store', '').strip()
        w.barcode        = request.form.get('barcode', '').strip()
        w.wishlist_notes = request.form.get('wishlist_notes', '').strip()
        db.session.add(w)
        db.session.commit()
        flash('Added to wishlist!', 'success')
        return redirect(url_for('wishlist'))
    return render_template('wishlist_form.html')


# ── API ───────────────────────────────────────────────────────────────────────

@app.route('/api/barcode-lookup')
@login_required
def barcode_lookup():
    code = request.args.get('code', '').strip()
    if not code:
        return jsonify({'found': False})
    existing = Whisky.query.filter_by(user_id=current_user.id, barcode=code).first()
    if existing:
        return jsonify({'found': True, 'id': existing.id, 'name': existing.name,
                        'wishlist': existing.wishlist})
    return jsonify({'found': False})


@app.route('/api/photo/<path:filename>')
@login_required
def serve_photo(filename):
    # Prevent path traversal: strip any directory components
    safe_name = os.path.basename(filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], safe_name)
    if not os.path.isfile(path):
        abort(404)
    return send_file(path)


# ── Export ────────────────────────────────────────────────────────────────────

@app.route('/export/csv')
@login_required
def export_csv():
    whiskies = (Whisky.query
                .filter_by(user_id=current_user.id, wishlist=False)
                .order_by(Whisky.name).all())
    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow(['Name', 'Distillery', 'Region', 'Age', 'ABV', 'Barcode',
                     'Status', 'Retired', 'Price', 'Store',
                     'Flavor Profile', 'Score',
                     'Nose', 'Palate', 'Finish', 'Notes', 'Added'])
    for w in whiskies:
        writer.writerow([
            w.name, w.distillery, w.region, w.age, w.abv, w.barcode,
            w.status, 'Yes' if w.retired else 'No',
            w.price, w.store,
            w.flavor_profile, w.score,
            w.nose, w.palate, w.finish, w.notes,
            w.created_at.strftime('%Y-%m-%d'),
        ])
    output = io.BytesIO()
    output.write(si.getvalue().encode('utf-8-sig'))   # utf-8-sig for Excel compat
    output.seek(0)
    return send_file(output, mimetype='text/csv',
                     download_name='whiskywise_export.csv', as_attachment=True)


# ── Startup ───────────────────────────────────────────────────────────────────

_init_db()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
