import os
import csv
import io
from datetime import datetime
from functools import wraps

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
    is_admin      = db.Column(db.Boolean, default=False, nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    @property
    def whisky_count(self):
        return Whisky.query.filter_by(user_id=self.id, wishlist=False).count()


class Whisky(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name          = db.Column(db.String(200), nullable=False)
    distillery    = db.Column(db.String(200))
    region        = db.Column(db.String(100))
    age           = db.Column(db.String(20))
    abv           = db.Column(db.Float)
    barcode       = db.Column(db.String(100))

    status        = db.Column(db.String(20), default='stashed')
    retired       = db.Column(db.Boolean, default=False)
    price         = db.Column(db.Float)
    store         = db.Column(db.String(200))

    notes         = db.Column(db.Text)
    nose          = db.Column(db.Text)
    palate        = db.Column(db.Text)
    finish        = db.Column(db.Text)
    flavor_profile = db.Column(db.String(50))
    score         = db.Column(db.Float)

    photo_front   = db.Column(db.String(300))
    photo_back    = db.Column(db.String(300))
    photo_cask    = db.Column(db.String(300))
    photo_barcode = db.Column(db.String(300))

    wishlist       = db.Column(db.Boolean, default=False)
    wishlist_notes = db.Column(db.Text)

    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref='whiskies')


@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, int(uid))


# ── Decorators ────────────────────────────────────────────────────────────────

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ── Helpers ───────────────────────────────────────────────────────────────────

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_photo(file, whisky_id, slot):
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
    w.name           = form.get('name', '').strip()
    w.distillery     = form.get('distillery', '').strip()
    w.region         = form.get('region', '').strip()
    w.age            = form.get('age', '').strip()
    w.abv            = _float_or_none(form.get('abv'))
    w.barcode        = form.get('barcode', '').strip()
    w.status         = form.get('status', 'stashed')
    w.retired        = form.get('retired') == 'on'
    w.price          = _float_or_none(form.get('price'))
    w.store          = form.get('store', '').strip()
    w.notes          = form.get('notes', '').strip()
    w.nose           = form.get('nose', '').strip()
    w.palate         = form.get('palate', '').strip()
    w.finish         = form.get('finish', '').strip()
    w.flavor_profile = form.get('flavor_profile', '').strip()
    w.score          = _float_or_none(form.get('score'))
    w.wishlist_notes = form.get('wishlist_notes', '').strip()


def _handle_photos(w, files):
    for slot in ('front', 'back', 'cask', 'barcode'):
        f = files.get(f'photo_{slot}')
        if f and f.filename:
            saved = save_photo(f, w.id, slot)
            if saved:
                setattr(w, f'photo_{slot}', saved)


def _validate_username(username, exclude_id=None):
    """Return error string or None if valid."""
    username = username.strip()
    if not username:
        return 'Username cannot be empty.'
    if len(username) < 3:
        return 'Username must be at least 3 characters.'
    if len(username) > 40:
        return 'Username must be 40 characters or fewer.'
    import re
    if not re.match(r'^[a-zA-Z0-9_\-\.]+$', username):
        return 'Username may only contain letters, numbers, underscores, hyphens and dots.'
    q = User.query.filter_by(username=username)
    if exclude_id:
        q = q.filter(User.id != exclude_id)
    if q.first():
        return f'Username "{username}" is already taken.'
    return None


def _init_db():
    with app.app_context():
        db.create_all()
        # Add is_admin column to existing DBs that predate this migration
        try:
            db.session.execute(db.text('ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0'))
            db.session.commit()
        except Exception:
            db.session.rollback()
        # Ensure first user (id=1) is always admin
        first = User.query.order_by(User.id).first()
        if not first:
            admin = User(username='admin', is_admin=True)
            admin.set_password('whiskywise')
            db.session.add(admin)
            db.session.commit()
            print("[WhiskyWise] Default admin created — username: admin  password: whiskywise")
        else:
            if not first.is_admin:
                first.is_admin = True
                db.session.commit()


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username', '').strip()).first()
        if user and user.check_password(request.form.get('password', '')):
            login_user(user, remember=True)
            return redirect(request.args.get('next') or url_for('index'))
        flash('Invalid username or password.', 'error')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Self-service: change own username and/or password."""
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'change_username':
            new_name = request.form.get('username', '').strip()
            err = _validate_username(new_name, exclude_id=current_user.id)
            if err:
                flash(err, 'error')
            else:
                current_user.username = new_name
                db.session.commit()
                flash('Username updated successfully.', 'success')

        elif action == 'change_password':
            if not current_user.check_password(request.form.get('current', '')):
                flash('Current password is incorrect.', 'error')
            elif request.form.get('new') != request.form.get('confirm'):
                flash('New passwords do not match.', 'error')
            elif len(request.form.get('new', '')) < 6:
                flash('Password must be at least 6 characters.', 'error')
            else:
                current_user.set_password(request.form['new'])
                db.session.commit()
                flash('Password changed successfully.', 'success')

    return render_template('settings.html')


# ── Admin panel ───────────────────────────────────────────────────────────────

@app.route('/admin')
@login_required
@admin_required
def admin_panel():
    users = User.query.order_by(User.id).all()
    return render_template('admin.html', users=users)


@app.route('/admin/user/new', methods=['POST'])
@login_required
@admin_required
def admin_create_user():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    is_admin = request.form.get('is_admin') == 'on'

    err = _validate_username(username)
    if err:
        flash(err, 'error')
        return redirect(url_for('admin_panel'))
    if len(password) < 6:
        flash('Password must be at least 6 characters.', 'error')
        return redirect(url_for('admin_panel'))

    u = User(username=username, is_admin=is_admin)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    flash(f'User "{username}" created.', 'success')
    return redirect(url_for('admin_panel'))


@app.route('/admin/user/<int:uid>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_user(uid):
    u = db.session.get(User, uid)
    if not u:
        abort(404)

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'rename':
            new_name = request.form.get('username', '').strip()
            err = _validate_username(new_name, exclude_id=uid)
            if err:
                flash(err, 'error')
            else:
                old_name = u.username
                u.username = new_name
                db.session.commit()
                flash(f'Renamed "{old_name}" → "{new_name}".', 'success')
                # Re-login current user if they renamed themselves
                if u.id == current_user.id:
                    login_user(u, remember=True)

        elif action == 'reset_password':
            new_pw = request.form.get('password', '').strip()
            if len(new_pw) < 6:
                flash('Password must be at least 6 characters.', 'error')
            else:
                u.set_password(new_pw)
                db.session.commit()
                flash(f'Password reset for "{u.username}".', 'success')

        elif action == 'toggle_admin':
            # Cannot demote yourself
            if u.id == current_user.id:
                flash('You cannot change your own admin status.', 'error')
            else:
                u.is_admin = not u.is_admin
                db.session.commit()
                state = 'granted' if u.is_admin else 'revoked'
                flash(f'Admin {state} for "{u.username}".', 'success')

        return redirect(url_for('admin_edit_user', uid=uid))

    return render_template('admin_edit_user.html', u=u)


@app.route('/admin/user/<int:uid>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(uid):
    u = db.session.get(User, uid)
    if not u:
        abort(404)
    if u.id == current_user.id:
        flash('You cannot delete your own account.', 'error')
        return redirect(url_for('admin_panel'))
    # Delete all their whiskies too
    Whisky.query.filter_by(user_id=u.id).delete()
    db.session.delete(u)
    db.session.commit()
    flash(f'User "{u.username}" and all their data deleted.', 'info')
    return redirect(url_for('admin_panel'))


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
        db.session.flush()
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
    output.write(si.getvalue().encode('utf-8-sig'))
    output.seek(0)
    return send_file(output, mimetype='text/csv',
                     download_name='whiskywise_export.csv', as_attachment=True)


# ── Error pages ───────────────────────────────────────────────────────────────

@app.errorhandler(403)
def forbidden(e):
    return render_template('403.html'), 403


# ── Startup ───────────────────────────────────────────────────────────────────

_init_db()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
