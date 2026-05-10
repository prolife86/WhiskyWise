import os
import re
import csv
import io
import secrets
from datetime import datetime, timezone
from functools import wraps
from urllib.parse import urlparse
from flask import (Flask, render_template, request, redirect, url_for,
                   flash, jsonify, send_file, abort, session)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect, CSRFError
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image, ImageOps

app = Flask(__name__)

# ── Version ───────────────────────────────────────────────────────────────────
APP_VERSION = os.environ.get('APP_VERSION', 'dev')

# ── Config ────────────────────────────────────────────────────────────────────
# Fix 8: Guard against weak/missing SECRET_KEY — generate an ephemeral random
# key rather than silently using a predictable placeholder.
_secret_key = os.environ.get('SECRET_KEY', '')
_known_placeholders = {'', 'dev-secret-change-me', 'change-this-to-a-long-random-secret', 'change-me-in-production'}
if _secret_key in _known_placeholders:
    _secret_key = secrets.token_hex(32)
    import logging
    logging.getLogger(__name__).warning(
        "[WhiskyWise] SECRET_KEY is not set or uses a placeholder. "
        "An ephemeral random key has been generated — sessions will not "
        "survive a container restart. Set SECRET_KEY in docker-compose.yml."
    )
app.config['SECRET_KEY'] = _secret_key

# Always resolve to absolute path so SQLite opens the right file regardless of cwd
db_path = os.path.abspath(os.environ.get('DATABASE_PATH', 'data/db/whiskywise.db'))
_db_dir = os.path.dirname(db_path)
if _db_dir:
    os.makedirs(_db_dir, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

upload_folder = os.path.abspath(os.environ.get('UPLOAD_FOLDER', 'data/uploads'))
os.makedirs(upload_folder, exist_ok=True)
app.config['UPLOAD_FOLDER'] = upload_folder
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024  # 64 MB
app.config['WTF_CSRF_ENABLED'] = True
# Fix 1: cookie hardening
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['REMEMBER_COOKIE_HTTPONLY'] = True
app.config['REMEMBER_COOKIE_SAMESITE'] = 'Lax'

# Fix 2: gif removed — it's converted to jpg anyway and adds unnecessary attack surface
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

MIN_PASSWORD_LEN = 8  # enforced everywhere a password is set or changed

# Fix 1: Pillow decompression bomb guard (40 MP cap)
Image.MAX_IMAGE_PIXELS = 40_000_000

DOMINANT_FLAVOURS = [
    # Core profiles (alphabetical)
    'floral', 'fresh', 'fruity', 'malty', 'medicinal',
    'oily', 'peaty', 'smoky', 'spicy', 'sweet',
    'vanilla', 'vegetative', 'woody',
    # Catch-all profiles
    'mixed', 'undefinable', 'complicated',
]

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],          # No global limit — only applied where decorated
    storage_uri='memory://',    # In-process storage; fine for single-worker gunicorn
)

csrf = CSRFProtect(app)

# Fix 5: pre-compute a dummy hash used in the login route so the password
# check always runs regardless of whether the username exists, preventing
# timing-based username enumeration.
_DUMMY_HASH = generate_password_hash('__dummy__')

def render_radar_svg(whisky, interactive=False):
    """Return an inline SVG radar chart for a whisky's dominant flavour profile.

    The chart plots the 7 WhiskyWise flavor axes used by the form.
    When *whisky* is None (e.g. the new-whisky form) an empty placeholder
    ring is rendered.
    When *interactive* is True the SVG receives clickable pie-segment cells
    (class="radar-cell") so radarSetVal() in the form JS can handle them,
    and the data polygon uses the per-axis radar_* fields on the whisky.
    """
    # These 7 axes must match _RADAR_AXES in whisky_form.html JS exactly.
    labels = ['woody', 'smoky', 'cereal', 'floral', 'fruity', 'medicinal', 'fiery']
    n = len(labels)
    cx, cy, r = 160, 160, 110        # centre and outer radius of chart
    levels = 5                        # concentric grid rings (1–5)

    import math

    def point(idx, radius):
        """Return (x, y) for spoke *idx* at *radius* from centre."""
        angle = (idx / n * 2 * math.pi) - (math.pi / 2)
        return cx + radius * math.cos(angle), cy + radius * math.sin(angle)

    svg_parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 320" '
        'width="320" height="320" class="radar-svg">'
    ]

    # ── interactive cell polygons (render BEFORE grid so grid sits on top) ──
    if interactive:
        half_step = math.pi / n   # half the angular gap between spokes
        for i, axis in enumerate(labels):
            for lvl in range(1, levels + 1):
                r_inner = r * (lvl - 1) / levels
                r_outer = r * lvl / levels
                # Four corners of this cell: inner-left, inner-right,
                # outer-right, outer-left
                angle_left  = (i / n * 2 * math.pi) - (math.pi / 2) - half_step
                angle_right = (i / n * 2 * math.pi) - (math.pi / 2) + half_step
                pts_list = [
                    (cx + r_inner * math.cos(angle_left),  cy + r_inner * math.sin(angle_left)),
                    (cx + r_inner * math.cos(angle_right), cy + r_inner * math.sin(angle_right)),
                    (cx + r_outer * math.cos(angle_right), cy + r_outer * math.sin(angle_right)),
                    (cx + r_outer * math.cos(angle_left),  cy + r_outer * math.sin(angle_left)),
                ]
                pts_str = ' '.join(f'{x:.2f},{y:.2f}' for x, y in pts_list)
                svg_parts.append(
                    f'<polygon class="radar-cell" points="{pts_str}" '
                    f'fill="rgba(0,0,0,0)" stroke="none" '
                    f'style="cursor:pointer;" '
                    f'onmouseover="this.style.fill=\'rgba(200,131,42,0.18)\'" '
                    f'onmouseout="this.style.fill=\'rgba(0,0,0,0)\'" '
                    f'onclick="radarSetVal(\'{axis}\',{lvl})"/>'
                )

    # ── concentric grid rings ─────────────────────────────────────────────
    for lvl in range(1, levels + 1):
        ring_r = r * lvl / levels
        pts = ' '.join(f'{point(i, ring_r)[0]:.2f},{point(i, ring_r)[1]:.2f}'
                       for i in range(n))
        svg_parts.append(
            f'<polygon points="{pts}" fill="none" '
            f'stroke="#c8a96e" stroke-width="0.5" stroke-opacity="0.4" pointer-events="none"/>'
        )

    # ── spokes ────────────────────────────────────────────────────────────
    for i in range(n):
        x, y = point(i, r)
        svg_parts.append(
            f'<line x1="{cx}" y1="{cy}" x2="{x:.2f}" y2="{y:.2f}" '
            f'stroke="#c8a96e" stroke-width="0.5" stroke-opacity="0.4" pointer-events="none"/>'
        )

    # ── axis labels ───────────────────────────────────────────────────────
    for i, lbl in enumerate(labels):
        x, y = point(i, r + 18)
        svg_parts.append(
            f'<text x="{x:.2f}" y="{y:.2f}" text-anchor="middle" '
            f'dominant-baseline="middle" font-size="9" fill="#c8a96e" '
            f'font-family="sans-serif" pointer-events="none">{lbl}</text>'
        )

    # ── data polygon ──────────────────────────────────────────────────────
    if whisky is not None:
        if interactive:
            # In the form, use the dedicated per-axis radar_* fields (0–5 scale)
            def get_axis(axis):
                val = getattr(whisky, f'radar_{axis}', None)
                return int(val) if val is not None else 0

            data_pts = ' '.join(
                f'{point(i, r * get_axis(lbl) / levels)[0]:.2f},'
                f'{point(i, r * get_axis(lbl) / levels)[1]:.2f}'
                for i, lbl in enumerate(labels)
            )
        else:
            # Detail/read-only view: read the saved radar_* columns directly
            def get_axis_ro(axis):
                val = getattr(whisky, f'radar_{axis}', None)
                return int(val) if val is not None else 0

            data_pts = ' '.join(
                f'{point(i, r * get_axis_ro(lbl) / levels)[0]:.2f},'
                f'{point(i, r * get_axis_ro(lbl) / levels)[1]:.2f}'
                for i, lbl in enumerate(labels)
            )

        svg_parts.append(
            f'<polygon id="radar-polygon" points="{data_pts}" '
            f'fill="#c8a96e" fill-opacity="0.25" '
            f'stroke="#c8a96e" stroke-width="1.5" pointer-events="none"/>'
        )

        # dots
        if interactive:
            vals = [get_axis(lbl) for lbl in labels]
        else:
            vals = [get_axis_ro(lbl) for lbl in labels]

        for i, (lbl, v) in enumerate(zip(labels, vals)):
            if v > 0:
                px, py = point(i, r * v / levels)
                svg_parts.append(
                    f'<circle cx="{px:.2f}" cy="{py:.2f}" r="4" '
                    f'fill="#C8832A" stroke="#1A120A" stroke-width="1.5" '
                    f'class="radar-dot" pointer-events="none"/>'
                )
    else:
        # No whisky yet — emit an empty polygon so JS can update it
        if interactive:
            empty_pts = ' '.join(
                f'{point(i, 0)[0]:.2f},{point(i, 0)[1]:.2f}'
                for i in range(n)
            )
            svg_parts.append(
                f'<polygon id="radar-polygon" points="{empty_pts}" '
                f'fill="#c8a96e" fill-opacity="0.25" '
                f'stroke="#c8a96e" stroke-width="1.5" pointer-events="none"/>'
            )

    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)


@app.context_processor
def inject_globals():
    return {'app_version': APP_VERSION, 'render_radar_svg': render_radar_svg}

# Fix 1: security response headers on every response
@app.after_request
def set_security_headers(response):
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self';"
    )
    return response


# Redirect users who are still on the default password to the change-password
# page before they can access anything else.
_FORCE_PW_EXEMPT = {'force_change_password', 'logout', 'login',
                    'static', 'serve_photo',
                    # API routes — token auth clients skip this entirely
                    'api_create_token', 'api_list_tokens', 'api_revoke_token',
                    'api_stats', 'api_collection', 'api_wishlist',
                    'api_create_wishlist_item', 'api_update_wishlist_item',
                    'api_whisky_detail', 'api_create_whisky', 'api_update_whisky',
                    'api_delete_whisky', 'api_upload_photo', 'api_delete_photo',
                    'barcode_lookup', 'rotate_photo',
                    'api_list_sessions', 'api_revoke_session',
                    'admin_sessions', 'admin_revoke_token', 'admin_revoke_session',
                    'settings_revoke_session', 'settings_revoke_token'}

@app.before_request
def enforce_password_change():
    """If the session carries the must_change_password flag, keep the user on
    the dedicated change-password page until they comply."""
    if not session.get('must_change_password'):
        return
    if request.endpoint in _FORCE_PW_EXEMPT:
        return
    # API Bearer-token requests are never flagged — they have no session
    if request.headers.get('Authorization', '').startswith('Bearer '):
        return
    return redirect(url_for('force_change_password'))


@app.before_request
def update_browser_session_activity():
    """Keep browser session last_seen fresh on every authenticated page load."""
    sid = session.get('browser_session_id')
    if not sid or not current_user.is_authenticated:
        return
    # Only update on real page requests, not static assets
    if request.endpoint and request.endpoint.startswith('static'):
        return
    try:
        bsrow = BrowserSession.query.filter_by(session_id=sid, user_id=current_user.id).first()
        if bsrow:
            # Throttle writes: only update if more than 60 seconds have elapsed
            now = datetime.now(timezone.utc)
            last = bsrow.last_seen
            if last is None or (now - last.replace(tzinfo=timezone.utc) if last.tzinfo is None else now - last).total_seconds() > 60:
                bsrow.last_seen = now
                db.session.commit()
    except Exception:
        db.session.rollback()

# ── Models ────────────────────────────────────────────────────────────────────
class User(UserMixin, db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin      = db.Column(db.Boolean, default=False, nullable=False)
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    @property
    def whisky_count(self):
        return Whisky.query.filter_by(user_id=self.id, wishlist=False).count()


class Whisky(db.Model):
    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name           = db.Column(db.String(200), nullable=False)
    distillery     = db.Column(db.String(200))
    region         = db.Column(db.String(100))
    age            = db.Column(db.String(20))
    abv            = db.Column(db.Float)
    barcode        = db.Column(db.String(100))
    status         = db.Column(db.String(20), default='stashed')
    retired        = db.Column(db.Boolean, default=False)
    price          = db.Column(db.Float)
    store          = db.Column(db.String(200))
    notes          = db.Column(db.Text)
    nose           = db.Column(db.Text)
    palate         = db.Column(db.Text)
    finish         = db.Column(db.Text)
    flavor_profile = db.Column(db.String(50))
    score          = db.Column(db.Float)   # NULL = unscored; 0.0 is a valid score
    # Radar chart axes — each stored as an integer 0–5 (0 = unset)
    radar_woody      = db.Column(db.Integer, default=0)
    radar_smoky      = db.Column(db.Integer, default=0)
    radar_cereal     = db.Column(db.Integer, default=0)
    radar_floral     = db.Column(db.Integer, default=0)
    radar_fruity     = db.Column(db.Integer, default=0)
    radar_medicinal  = db.Column(db.Integer, default=0)
    radar_fiery      = db.Column(db.Integer, default=0)
    photo_front    = db.Column(db.String(300))
    photo_back     = db.Column(db.String(300))
    photo_cask     = db.Column(db.String(300))
    photo_barcode  = db.Column(db.String(300))
    wishlist       = db.Column(db.Boolean, default=False)
    wishlist_notes = db.Column(db.Text)
    created_at     = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at     = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref='whiskies')


class ApiToken(db.Model):
    """Personal API tokens for mobile / third-party clients.

    Each token is a 32-byte hex string stored as a SHA-256 digest so that a
    database leak does not expose live credentials.  The raw token is shown
    to the user exactly once (at creation time) and never stored in plain
    text.

    ``origin_ip``      — IP address of the request that created the token.
    ``client_version`` — version string sent by the client (e.g. Android app
                         version).  Populated from the ``X-Client-Version``
                         request header when the token is created; updated on
                         every authenticated request so it always reflects the
                         latest known version of that client.
    """
    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name           = db.Column(db.String(100), nullable=False)          # human label
    token_hash     = db.Column(db.String(64), unique=True, nullable=False)
    created_at     = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_used      = db.Column(db.DateTime, nullable=True)
    origin_ip      = db.Column(db.String(45), nullable=True)   # IPv4 or IPv6
    client_version = db.Column(db.String(50), nullable=True)   # e.g. "1.2.3"

    user = db.relationship('User', backref='api_tokens')

    @staticmethod
    def hash(raw: str) -> str:
        import hashlib
        return hashlib.sha256(raw.encode()).hexdigest()

    @classmethod
    def create(cls, user_id: int, name: str, origin_ip: str = None,
               client_version: str = None):
        """Generate a new token, persist its hash, and return the raw value."""
        raw = secrets.token_hex(32)
        token = cls(
            user_id=user_id,
            name=name,
            token_hash=cls.hash(raw),
            origin_ip=origin_ip,
            client_version=client_version,
        )
        db.session.add(token)
        db.session.commit()
        return raw, token

    @classmethod
    def lookup(cls, raw: str):
        """Return the ApiToken row for *raw*, or None if invalid."""
        return cls.query.filter_by(token_hash=cls.hash(raw)).first()


class BrowserSession(db.Model):
    """Tracks active browser (cookie-based) login sessions.

    A row is inserted on every successful web login and deleted on logout or
    admin revocation.  The ``session_id`` is a random hex token stored in the
    Flask server-side session so the browser can be matched to its DB row.

    ``origin_ip``      — remote address at login time.
    ``client_version`` — Docker image version (APP_VERSION) recorded at login.
    ``user_agent``     — truncated User-Agent header for display.
    ``last_seen``      — updated on each authenticated page request.
    """
    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    session_id     = db.Column(db.String(64), unique=True, nullable=False)
    created_at     = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen      = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    origin_ip      = db.Column(db.String(45), nullable=True)
    client_version = db.Column(db.String(50), nullable=True)
    user_agent     = db.Column(db.String(200), nullable=True)

    user = db.relationship('User', backref='browser_sessions')

    @classmethod
    def create(cls, user_id: int, origin_ip: str = None,
               client_version: str = None, user_agent: str = None):
        """Create a new session record and return (session_id, row)."""
        sid = secrets.token_hex(32)
        row = cls(
            user_id=user_id,
            session_id=sid,
            origin_ip=origin_ip,
            client_version=client_version,
            user_agent=(user_agent or '')[:200],
        )
        db.session.add(row)
        db.session.commit()
        return sid, row


@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, int(uid))

# ── Decorators ────────────────────────────────────────────────────────────────
def admin_required(f):
    """Must be stacked INSIDE @login_required so unauthenticated users get
    redirected to login rather than receiving a bare 403."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
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
        f"w{whisky_id}_{slot}_{int(datetime.now(timezone.utc).timestamp())}.{save_ext}"
    )
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    try:
        img = Image.open(file)
        # Auto-correct EXIF orientation so portrait photos aren't sideways
        img = ImageOps.exif_transpose(img)
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
    """Convert form string to float, returning None for empty/missing values.
    Correctly handles '0' and '0.0' as valid zero scores."""
    if val is None or str(val).strip() == '':
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _fill_whisky(w, form):
    """Populate whisky fields from a form dict. Does NOT touch w.wishlist."""
    w.name           = form.get('name', '').strip()[:200]
    w.distillery     = form.get('distillery', '').strip()[:200]
    w.region         = form.get('region', '').strip()[:100]
    w.age            = form.get('age', '').strip()[:20]
    w.abv            = _float_or_none(form.get('abv'))
    w.barcode        = form.get('barcode', '').strip()[:100]
    _VALID_STATUSES = {'stashed', 'open', 'finished'}
    raw_status = form.get('status', 'stashed')
    w.status         = raw_status if raw_status in _VALID_STATUSES else 'stashed'
    w.retired        = form.get('retired') == 'on'
    w.price          = _float_or_none(form.get('price'))
    w.store          = form.get('store', '').strip()[:200]
    w.notes          = form.get('notes', '').strip()[:4000]
    w.nose           = form.get('nose', '').strip()[:4000]
    w.palate         = form.get('palate', '').strip()[:4000]
    w.finish         = form.get('finish', '').strip()[:4000]
    w.flavor_profile = form.get('flavor_profile', '').strip()[:50]
    w.score          = _float_or_none(form.get('score'))
    w.wishlist_notes = form.get('wishlist_notes', '').strip()[:4000]
    # Radar axes — clamp to 0–5
    for axis in ('woody', 'smoky', 'cereal', 'floral', 'fruity', 'medicinal', 'fiery'):
        val = _float_or_none(form.get(f'radar_{axis}'))
        setattr(w, f'radar_{axis}', max(0, min(5, int(val))) if val is not None else 0)
    w.updated_at     = datetime.now(timezone.utc)


def _delete_photo_file(filename):
    """Remove a photo file from disk. Silently ignores missing files."""
    if not filename:
        return
    path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(filename))
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except Exception as exc:
        app.logger.warning("Could not delete photo file %s: %s", filename, exc)


def _delete_all_photos(w):
    """Delete all photo files on disk for a whisky record."""
    for slot in ('photo_front', 'photo_back', 'photo_cask', 'photo_barcode'):
        _delete_photo_file(getattr(w, slot))



def _handle_photos(w, files):
    for slot in ('front', 'back', 'cask', 'barcode'):
        f = files.get(f'photo_{slot}')
        if f and f.filename:
            saved = save_photo(f, w.id, slot)
            if saved:
                _delete_photo_file(getattr(w, f'photo_{slot}'))
                setattr(w, f'photo_{slot}', saved)


# ── Mobile API helpers ────────────────────────────────────────────────────────
def api_login_required(f):
    """Decorator that accepts EITHER a session cookie (browser) OR a Bearer
    token in the Authorization header (mobile app).

    Priority: Bearer token > session cookie.
    On failure returns JSON 401 instead of redirecting to the login page.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            raw = auth_header[7:].strip()
            token_row = ApiToken.lookup(raw)
            if not token_row:
                return jsonify({'error': 'Invalid or expired token.'}), 401
            # Stamp last_used, and refresh IP + client_version so they always
            # reflect the most recent request rather than just the login call.
            try:
                token_row.last_used = datetime.now(timezone.utc)
                current_ip = request.headers.get('X-Forwarded-For', request.remote_addr or '').split(',')[0].strip()
                if current_ip:
                    token_row.origin_ip = current_ip
                client_ver = request.headers.get('X-Client-Version', '').strip()
                if client_ver:
                    token_row.client_version = client_ver[:50]
                db.session.commit()
            except Exception:
                db.session.rollback()
            # Temporarily set flask-login's current_user for the duration of
            # this request so all existing helpers keep working unchanged.
            from flask_login import login_user as _lu
            _lu(token_row.user, remember=False)
            return f(*args, **kwargs)
        # Fall back to session-cookie auth (normal browser flow)
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required.'}), 401
        # Update browser session last_seen (best-effort)
        sid = session.get('browser_session_id')
        if sid:
            try:
                bsrow = BrowserSession.query.filter_by(session_id=sid).first()
                if bsrow:
                    bsrow.last_seen = datetime.now(timezone.utc)
                    db.session.commit()
            except Exception:
                db.session.rollback()
        return f(*args, **kwargs)
    return decorated


def _whisky_to_dict(w):
    """Serialise a Whisky ORM object to a JSON-safe dict."""
    def photo_url(filename):
        if not filename:
            return None
        return url_for('serve_photo', filename=filename, _external=False)

    return {
        'id':             w.id,
        'name':           w.name,
        'distillery':     w.distillery,
        'region':         w.region,
        'age':            w.age,
        'abv':            w.abv,
        'barcode':        w.barcode,
        'status':         w.status,
        'retired':        w.retired,
        'price':          w.price,
        'store':          w.store,
        'notes':          w.notes,
        'nose':           w.nose,
        'palate':         w.palate,
        'finish':         w.finish,
        'flavor_profile': w.flavor_profile,
        'score':          w.score,
        'radar': {
            'woody':     w.radar_woody     or 0,
            'smoky':     w.radar_smoky     or 0,
            'cereal':    w.radar_cereal    or 0,
            'floral':    w.radar_floral    or 0,
            'fruity':    w.radar_fruity    or 0,
            'medicinal': w.radar_medicinal or 0,
            'fiery':     w.radar_fiery     or 0,
        },
        'wishlist':       w.wishlist,
        'wishlist_notes': w.wishlist_notes,
        'photo_front':    photo_url(w.photo_front),
        'photo_back':     photo_url(w.photo_back),
        'photo_cask':     photo_url(w.photo_cask),
        'photo_barcode':  photo_url(w.photo_barcode),
        'created_at':     w.created_at.isoformat() if w.created_at else None,
        'updated_at':     w.updated_at.isoformat() if w.updated_at else None,
    }


def _str_or_none(val, maxlen):
    """Return a stripped, length-capped string, or None if val is None/empty.

    Prevents str(None) = 'None' being written to the DB when a mobile client
    explicitly sends null to clear a field.
    """
    if val is None:
        return None
    return str(val).strip()[:maxlen] or None


def _fill_whisky_from_json(w, data):
    """Populate whisky fields from a parsed JSON dict (mobile POST/PUT body).

    Fields present in *data* are updated; absent fields are left unchanged.
    A field sent as JSON ``null`` is treated as an explicit clear (set to None
    in the DB), so mobile clients can erase optional fields by including the key
    with a null value rather than omitting it entirely.
    """
    if 'name'           in data: w.name           = str(data['name']).strip()[:200]
    if 'distillery'     in data: w.distillery      = _str_or_none(data['distillery'], 200)
    if 'region'         in data: w.region          = _str_or_none(data['region'],      100)
    if 'age'            in data: w.age             = _str_or_none(data['age'],          20)
    if 'abv'            in data: w.abv             = _float_or_none(data['abv'])
    if 'barcode'        in data: w.barcode         = _str_or_none(data['barcode'],     100)
    _VALID_STATUSES = {'stashed', 'open', 'finished'}
    if 'status' in data:
        raw_status = str(data['status'])
        w.status = raw_status if raw_status in _VALID_STATUSES else 'stashed'
    if 'retired'        in data: w.retired         = bool(data['retired'])
    if 'price'          in data: w.price           = _float_or_none(data['price'])
    if 'store'          in data: w.store           = _str_or_none(data['store'],       200)
    if 'notes'          in data: w.notes           = _str_or_none(data['notes'],      4000)
    if 'nose'           in data: w.nose            = _str_or_none(data['nose'],       4000)
    if 'palate'         in data: w.palate          = _str_or_none(data['palate'],     4000)
    if 'finish'         in data: w.finish          = _str_or_none(data['finish'],     4000)
    if 'flavor_profile' in data: w.flavor_profile  = _str_or_none(data['flavor_profile'], 50)
    if 'score'          in data: w.score           = _float_or_none(data['score'])
    if 'wishlist_notes' in data: w.wishlist_notes  = _str_or_none(data['wishlist_notes'], 4000)
    # Radar axes — accept either a nested dict {"radar": {"smoky": 3, ...}}
    # or flat keys {"radar_smoky": 3, ...}.  Values are clamped to 0–5.
    radar_data = data.get('radar', {})
    for axis in ('woody', 'smoky', 'cereal', 'floral', 'fruity', 'medicinal', 'fiery'):
        val = radar_data.get(axis, data.get(f'radar_{axis}'))
        if val is not None:
            setattr(w, f'radar_{axis}', max(0, min(5, int(val))))
    w.updated_at = datetime.now(timezone.utc)


def _validate_username(username, exclude_id=None):
    """Return error string or None if valid."""
    username = username.strip()
    if not username:
        return 'Username cannot be empty.'
    if len(username) < 3:
        return 'Username must be at least 3 characters.'
    if len(username) > 40:
        return 'Username must be 40 characters or fewer.'
    if not re.match(r'^[a-zA-Z0-9_\-\.]+$', username):
        return 'Username may only contain letters, numbers, underscores, hyphens and dots.'
    q = User.query.filter_by(username=username)
    if exclude_id:
        q = q.filter(User.id != exclude_id)
    if q.first():
        return f'Username "{username}" is already taken.'
    return None


def _safe_next(next_url):
    """Only allow relative redirects to prevent open-redirect attacks."""
    if not next_url:
        return None
    parsed = urlparse(next_url)
    # Reject anything with a scheme or netloc (i.e. absolute/external URLs)
    if parsed.scheme or parsed.netloc:
        return None
    return next_url


def _init_db():
    with app.app_context():
        db.create_all()   # also creates api_token / browser_session tables on first run
        # Enable WAL mode here (Flask-SQLAlchemy 3.x no longer supports
        # accessing db.engine at module scope outside an app context)
        with db.engine.connect() as _wal_conn:
            _wal_conn.execute(db.text('PRAGMA journal_mode=WAL'))
        conn = db.engine.raw_connection()
        try:
            cur = conn.cursor()
            try:
                cols = [row[1] for row in cur.execute('PRAGMA table_info("user")').fetchall()]
                if 'is_admin' not in cols:
                    cur.execute('ALTER TABLE "user" ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0')
                    conn.commit()
                    print("[WhiskyWise] Migrated DB: added is_admin column.")
            except Exception as exc:
                conn.rollback()
                print(f"[WhiskyWise] WARNING: DB migration check failed — "
                      f"the app may still work but please verify the 'user' table schema. "
                      f"Error: {exc}")
            # Migrate api_token table — add new columns if they don't exist yet
            try:
                token_cols = [row[1] for row in cur.execute('PRAGMA table_info("api_token")').fetchall()]
                if 'origin_ip' not in token_cols:
                    cur.execute('ALTER TABLE "api_token" ADD COLUMN origin_ip VARCHAR(45)')
                    conn.commit()
                    print("[WhiskyWise] Migrated DB: added origin_ip to api_token.")
                if 'client_version' not in token_cols:
                    cur.execute('ALTER TABLE "api_token" ADD COLUMN client_version VARCHAR(50)')
                    conn.commit()
                    print("[WhiskyWise] Migrated DB: added client_version to api_token.")
            except Exception as exc:
                conn.rollback()
                print(f"[WhiskyWise] WARNING: api_token migration failed: {exc}")
        finally:
            conn.close()
        db.session.expire_all()

        first = User.query.order_by(User.id).first()
        if not first:
            admin = User(username='admin', is_admin=True)
            admin.set_password('whiskywise')
            db.session.add(admin)
            db.session.commit()
            print("[WhiskyWise] Default admin created — username: admin password: whiskywise")
        elif not first.is_admin:
            first.is_admin = True
            db.session.commit()
            print(f"[WhiskyWise] Promoted '{first.username}' to admin.")

# ── Auth ──────────────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username', '').strip()).first()
        # Fix 5: always call check_password_hash regardless of whether the user
        # exists so the response time is identical for unknown usernames and
        # wrong passwords, preventing timing-based username enumeration.
        pw_ok = check_password_hash(
            user.password_hash if user else _DUMMY_HASH,
            request.form.get('password', '')
        )
        if user and pw_ok:
            login_user(user, remember=True)
            # Flag the session if the user is still on the default password so
            # enforce_password_change() can redirect them before anything else.
            if user.check_password('whiskywise'):
                session['must_change_password'] = True
            # Record a browser session row for this login
            origin_ip = request.headers.get('X-Forwarded-For', request.remote_addr or '').split(',')[0].strip()
            ua = request.headers.get('User-Agent', '')
            try:
                sid, _ = BrowserSession.create(
                    user_id=user.id,
                    origin_ip=origin_ip or None,
                    client_version=APP_VERSION,
                    user_agent=ua,
                )
                session['browser_session_id'] = sid
            except Exception:
                db.session.rollback()
            # Validate next param to prevent open-redirect
            return redirect(_safe_next(request.args.get('next')) or url_for('index'))
        flash('Invalid username or password.', 'error')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    # Remove the browser session record from the DB
    sid = session.get('browser_session_id')
    if sid:
        try:
            bsrow = BrowserSession.query.filter_by(session_id=sid).first()
            if bsrow:
                db.session.delete(bsrow)
                db.session.commit()
        except Exception:
            db.session.rollback()
    logout_user()
    return redirect(url_for('login'))


@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def force_change_password():
    """Dedicated route shown when a user is still on the default password.

    Unlike the settings page this route does NOT ask for the current password
    (we already know it's the insecure default) but it does enforce the minimum
    length and requires a confirmation field.
    """
    if request.method == 'POST':
        new_pw  = request.form.get('new', '')
        confirm = request.form.get('confirm', '')
        if new_pw != confirm:
            flash('Passwords do not match.', 'error')
        elif len(new_pw) < MIN_PASSWORD_LEN:
            flash(f'Password must be at least {MIN_PASSWORD_LEN} characters.', 'error')
        elif new_pw == 'whiskywise':
            flash('Please choose a password different from the default.', 'error')
        else:
            current_user.set_password(new_pw)
            db.session.commit()
            session.pop('must_change_password', None)
            flash('Password updated successfully. Welcome!', 'success')
            return redirect(url_for('index'))
    return render_template('change_password.html', forced=True)


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
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
            elif len(request.form.get('new', '')) < MIN_PASSWORD_LEN:
                flash(f'Password must be at least {MIN_PASSWORD_LEN} characters.', 'error')
            else:
                current_user.set_password(request.form['new'])
                db.session.commit()
                flash('Password changed successfully.', 'success')
    # Collect session and token data for display
    current_sid = session.get('browser_session_id')
    raw_sessions = BrowserSession.query.filter_by(user_id=current_user.id).order_by(BrowserSession.id).all()
    # Annotate each with whether it is the current session
    browser_sessions = []
    for s in raw_sessions:
        s.current = (s.session_id == current_sid)
        browser_sessions.append(s)
    api_tokens = ApiToken.query.filter_by(user_id=current_user.id).order_by(ApiToken.id).all()
    return render_template('settings.html', browser_sessions=browser_sessions, api_tokens=api_tokens)


@app.route('/settings/session/<int:sid>/revoke', methods=['POST'])
@login_required
def settings_revoke_session(sid):
    """Self-service: user revokes one of their own browser sessions."""
    row = BrowserSession.query.filter_by(id=sid, user_id=current_user.id).first()
    if not row:
        flash('Session not found.', 'error')
    else:
        db.session.delete(row)
        db.session.commit()
        flash('Session revoked.', 'info')
    return redirect(url_for('settings'))


@app.route('/settings/token/<int:tid>/revoke', methods=['POST'])
@login_required
def settings_revoke_token(tid):
    """Self-service: user revokes one of their own API tokens."""
    row = ApiToken.query.filter_by(id=tid, user_id=current_user.id).first()
    if not row:
        flash('Token not found.', 'error')
    else:
        db.session.delete(row)
        db.session.commit()
        flash(f'Token "{row.name}" revoked.', 'info')
    return redirect(url_for('settings'))

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
    if len(password) < MIN_PASSWORD_LEN:
        flash(f'Password must be at least {MIN_PASSWORD_LEN} characters.', 'error')
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
                if u.id == current_user.id:
                    login_user(u, remember=True)
        elif action == 'reset_password':
            new_pw = request.form.get('password', '').strip()
            if len(new_pw) < MIN_PASSWORD_LEN:
                flash(f'Password must be at least {MIN_PASSWORD_LEN} characters.', 'error')
            else:
                u.set_password(new_pw)
                db.session.commit()
                flash(f'Password reset for "{u.username}".', 'success')
        elif action == 'toggle_admin':
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
    username = u.username
    # Delete photo files from disk before removing DB records
    for w in Whisky.query.filter_by(user_id=u.id).all():
        _delete_all_photos(w)
    # Use synchronize_session='fetch' so the ORM identity map stays consistent
    Whisky.query.filter_by(user_id=u.id).delete(synchronize_session='fetch')
    db.session.delete(u)
    db.session.commit()
    flash(f'User "{username}" and all their data deleted.', 'info')
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
    total         = Whisky.query.filter_by(user_id=current_user.id, wishlist=False).count()
    open_count    = Whisky.query.filter_by(user_id=current_user.id, status='open', wishlist=False).count()
    stashed_count = Whisky.query.filter_by(user_id=current_user.id, status='stashed', wishlist=False).count()
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
                           dominant_flavours=DOMINANT_FLAVOURS,
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
    return render_template('whisky_form.html', whisky=None, dominant_flavours=DOMINANT_FLAVOURS)


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
        db.session.commit()
        flash('Saved!', 'success')
        return redirect(url_for('whisky_detail', wid=w.id))
    return render_template('whisky_form.html', whisky=w, dominant_flavours=DOMINANT_FLAVOURS)


@app.route('/whisky/<int:wid>/delete', methods=['POST'])
@login_required
def delete_whisky(wid):
    w = Whisky.query.filter_by(id=wid, user_id=current_user.id).first_or_404()
    was_wishlist = w.wishlist
    _delete_all_photos(w)
    db.session.delete(w)
    db.session.commit()
    flash('Deleted.', 'info')
    return redirect(url_for('wishlist') if was_wishlist else url_for('collection'))


@app.route('/whisky/new-wishlist', methods=['GET', 'POST'])
@login_required
def new_wishlist_item():
    if request.method == 'POST':
        w = Whisky(user_id=current_user.id, wishlist=True)
        _fill_whisky(w, request.form)   # reuse shared field-filling logic
        db.session.add(w)
        db.session.commit()
        flash('Added to wishlist!', 'success')
        return redirect(url_for('wishlist'))
    return render_template('wishlist_form.html')


@app.route('/whisky/<int:wid>/edit-wishlist', methods=['GET', 'POST'])
@login_required
def edit_wishlist_item(wid):
    w = Whisky.query.filter_by(id=wid, user_id=current_user.id, wishlist=True).first_or_404()
    if request.method == 'POST':
        _fill_whisky(w, request.form)   # reuse shared field-filling logic
        db.session.commit()
        flash('Wishlist item updated.', 'success')
        return redirect(url_for('wishlist'))
    return render_template('wishlist_form.html', item=w)

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
@api_login_required
def serve_photo(filename):
    """Serve a photo file. Ownership is enforced by confirming the filename
    exists on a Whisky record that belongs to the current user."""
    safe_name = os.path.basename(filename)
    owned = Whisky.query.filter(
        Whisky.user_id == current_user.id,
        db.or_(
            Whisky.photo_front   == safe_name,
            Whisky.photo_back    == safe_name,
            Whisky.photo_cask    == safe_name,
            Whisky.photo_barcode == safe_name,
        )
    ).first()
    if not owned:
        abort(403)
    path = os.path.join(app.config['UPLOAD_FOLDER'], safe_name)
    if not os.path.isfile(path):
        abort(404)
    return send_file(path)


@csrf.exempt
@app.route('/api/photo/<int:wid>/<slot>/rotate', methods=['POST'])
@api_login_required
def rotate_photo(wid, slot):
    """Rotate a stored photo 90 degrees clockwise and re-save in place."""
    if slot not in ('front', 'back', 'cask', 'barcode'):
        abort(400)
    w = Whisky.query.filter_by(id=wid, user_id=current_user.id).first_or_404()
    filename = getattr(w, f'photo_{slot}')
    if not filename:
        abort(404)
    path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(filename))
    if not os.path.isfile(path):
        abort(404)
    try:
        img = Image.open(path)
        # Rotate 90° clockwise (expand=True keeps full image, no cropping)
        img = img.rotate(-90, expand=True)
        ext = filename.rsplit('.', 1)[1].lower()
        save_kwargs = {'optimize': True}
        if ext == 'jpg':
            if img.mode != 'RGB':
                img = img.convert('RGB')
            save_kwargs['quality'] = 85
        img.save(path, **save_kwargs)
    except Exception as exc:
        app.logger.error("Photo rotate failed: %s", exc)
        # Fix 4: don't leak internal exception detail (file paths etc.) to the client
        return jsonify({'ok': False, 'error': 'Rotation failed. Check server logs.'}), 500
    return jsonify({'ok': True})

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
                     'Dominant Flavour', 'Score',
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
    output.write(si.getvalue().encode('utf-8-sig'))  # BOM for Excel compatibility
    output.seek(0)
    return send_file(output, mimetype='text/csv',
                     download_name='whiskywise_export.csv', as_attachment=True)

# ── JSON API (mobile / third-party clients) ───────────────────────────────────
#
# Authentication
# --------------
# Every API endpoint accepts EITHER:
#   a) A session cookie (works seamlessly for browser-based callers), OR
#   b) An Authorization: Bearer <token> header (preferred for Android / iOS).
#
# Token lifecycle
# ---------------
#   POST   /api/auth/token          — exchange username+password for a token
#   GET    /api/auth/tokens         — list your tokens (name, id, last_used)
#   DELETE /api/auth/token/<tid>    — revoke a token
#
# Collection & wishlist
# ---------------------
#   GET    /api/v1/collection                — list collection (filterable)
#   GET    /api/v1/wishlist                  — list wishlist
#   GET    /api/v1/stats                     — dashboard counts + top-10
#   GET    /api/v1/whisky/<id>               — single whisky detail
#   POST   /api/v1/whisky                    — create whisky (JSON body)
#   PUT    /api/v1/whisky/<id>               — update whisky (JSON body)
#   DELETE /api/v1/whisky/<id>               — delete whisky
#   POST   /api/v1/whisky/<id>/photo/<slot>  — upload a photo (multipart)
#   DELETE /api/v1/whisky/<id>/photo/<slot>  — remove a photo
#   POST   /api/v1/wishlist                  — create wishlist item
#   PUT    /api/v1/wishlist/<id>             — update wishlist item
#
# Existing endpoints (unchanged, also work with Bearer tokens)
# -------------------------------------------------------------
#   GET    /api/barcode-lookup?code=...
#   GET    /api/photo/<filename>
#   POST   /api/photo/<wid>/<slot>/rotate
#
# All success responses: HTTP 200/201 with {"data": ...}
# All error responses:   HTTP 4xx     with {"error": "..."}
# ─────────────────────────────────────────────────────────────────────────────

# ── Token management ──────────────────────────────────────────────────────────

@csrf.exempt
@app.route('/api/auth/token', methods=['POST'])
@limiter.limit('10 per minute')
def api_create_token():
    """Exchange username + password for a Bearer token.

    Request body (JSON):
        {"username": "...", "password": "...", "name": "My Android phone"}

    Response:
        {"data": {"token": "<raw>", "id": <int>, "name": "..."}}

    The returned token must be stored securely by the client (e.g. Android
    EncryptedSharedPreferences) and sent as ``Authorization: Bearer <token>``
    on every subsequent request.
    """
    body = request.get_json(silent=True) or {}
    username = body.get('username', '').strip()
    password = body.get('password', '')
    label    = body.get('name', 'API token').strip() or 'API token'

    user = User.query.filter_by(username=username).first()
    pw_ok = check_password_hash(
        user.password_hash if user else _DUMMY_HASH, password
    )
    if not (user and pw_ok):
        return jsonify({'error': 'Invalid username or password.'}), 401

    origin_ip = request.headers.get('X-Forwarded-For', request.remote_addr or '').split(',')[0].strip()
    client_ver = request.headers.get('X-Client-Version', '').strip() or None
    raw, token_row = ApiToken.create(
        user_id=user.id,
        name=label,
        origin_ip=origin_ip or None,
        client_version=client_ver,
    )
    return jsonify({'data': {
        'token':    raw,
        'id':       token_row.id,
        'name':     token_row.name,
        'created':  token_row.created_at.isoformat(),
    }}), 201


@app.route('/api/auth/tokens')
@api_login_required
def api_list_tokens():
    """List all API tokens belonging to the authenticated user.

    Token values are never returned — only metadata.
    """
    tokens = ApiToken.query.filter_by(user_id=current_user.id).order_by(ApiToken.id).all()
    return jsonify({'data': [
        {
            'id':             t.id,
            'name':           t.name,
            'created':        t.created_at.isoformat(),
            'last_used':      t.last_used.isoformat() if t.last_used else None,
            'origin_ip':      t.origin_ip,
            'client_version': t.client_version,
        }
        for t in tokens
    ]})


@csrf.exempt
@app.route('/api/auth/token/<int:tid>', methods=['DELETE'])
@api_login_required
def api_revoke_token(tid):
    """Revoke (delete) one of the authenticated user's API tokens."""
    token_row = ApiToken.query.filter_by(id=tid, user_id=current_user.id).first()
    if not token_row:
        return jsonify({'error': 'Token not found.'}), 404
    db.session.delete(token_row)
    db.session.commit()
    return jsonify({'data': {'revoked': tid}})


# ── Browser session management ────────────────────────────────────────────────

@app.route('/api/auth/sessions')
@api_login_required
def api_list_sessions():
    """List all active browser sessions for the authenticated user."""
    rows = BrowserSession.query.filter_by(user_id=current_user.id).order_by(BrowserSession.id).all()
    current_sid = session.get('browser_session_id')
    return jsonify({'data': [
        {
            'id':             r.id,
            'created':        r.created_at.isoformat(),
            'last_seen':      r.last_seen.isoformat() if r.last_seen else None,
            'origin_ip':      r.origin_ip,
            'client_version': r.client_version,
            'user_agent':     r.user_agent,
            'current':        r.session_id == current_sid,
        }
        for r in rows
    ]})


@csrf.exempt
@app.route('/api/auth/session/<int:sid>', methods=['DELETE'])
@api_login_required
def api_revoke_session(sid):
    """Revoke (delete) one of the authenticated user's browser sessions."""
    row = BrowserSession.query.filter_by(id=sid, user_id=current_user.id).first()
    if not row:
        return jsonify({'error': 'Session not found.'}), 404
    db.session.delete(row)
    db.session.commit()
    return jsonify({'data': {'revoked': sid}})


# ── Admin session/token management ───────────────────────────────────────────

@app.route('/admin/sessions')
@login_required
@admin_required
def admin_sessions():
    """Admin view: all API tokens and browser sessions across all users."""
    users = User.query.order_by(User.id).all()
    api_tokens = ApiToken.query.order_by(ApiToken.user_id, ApiToken.id).all()
    browser_sessions = BrowserSession.query.order_by(BrowserSession.user_id, BrowserSession.id).all()
    return render_template(
        'admin_sessions.html',
        users=users,
        api_tokens=api_tokens,
        browser_sessions=browser_sessions,
    )


@app.route('/admin/sessions/token/<int:tid>/revoke', methods=['POST'])
@login_required
@admin_required
def admin_revoke_token(tid):
    """Admin: revoke any user's API token."""
    token_row = db.session.get(ApiToken, tid)
    if not token_row:
        flash('Token not found.', 'error')
    else:
        db.session.delete(token_row)
        db.session.commit()
        flash(f'API token #{tid} revoked.', 'info')
    return redirect(url_for('admin_sessions'))


@app.route('/admin/sessions/browser/<int:sid>/revoke', methods=['POST'])
@login_required
@admin_required
def admin_revoke_session(sid):
    """Admin: revoke any user's browser session."""
    row = db.session.get(BrowserSession, sid)
    if not row:
        flash('Session not found.', 'error')
    else:
        db.session.delete(row)
        db.session.commit()
        flash(f'Browser session #{sid} revoked.', 'info')
    return redirect(url_for('admin_sessions'))


# ── Stats / dashboard ─────────────────────────────────────────────────────────

@app.route('/api/v1/stats')
@api_login_required
def api_stats():
    """Return the same summary data shown on the web dashboard."""
    top10 = (Whisky.query
             .filter_by(user_id=current_user.id, wishlist=False)
             .filter(Whisky.score.isnot(None))
             .order_by(Whisky.score.desc())
             .limit(10).all())
    return jsonify({'data': {
        'total':          Whisky.query.filter_by(user_id=current_user.id, wishlist=False).count(),
        'open':           Whisky.query.filter_by(user_id=current_user.id, status='open',    wishlist=False).count(),
        'stashed':        Whisky.query.filter_by(user_id=current_user.id, status='stashed', wishlist=False).count(),
        'wishlist_count': Whisky.query.filter_by(user_id=current_user.id, wishlist=True).count(),
        'top10':          [_whisky_to_dict(w) for w in top10],
        'dominant_flavours': DOMINANT_FLAVOURS,
    }})


# ── Collection ────────────────────────────────────────────────────────────────

@app.route('/api/v1/collection')
@api_login_required
def api_collection():
    """Return the user's collection as a JSON array.

    Optional query parameters mirror the web collection filters:
        q           — free-text search (name, distillery, barcode, region)
        flavor      — exact dominant flavour match (see /api/v1/stats for full list)
        min_score   — float, inclusive lower bound on score
        max_price   — float, inclusive upper bound on price
        status      — 'open' | 'stashed' | 'retired'
        sort        — 'score' (default) | 'name' | 'added' | 'price'
        order       — 'desc' (default) | 'asc'
        limit       — int, max results (default 200, max 500)
        offset      — int, pagination offset (default 0)
    """
    q             = request.args.get('q', '').strip()
    flavor        = request.args.get('flavor', '')
    min_score     = request.args.get('min_score', '')
    max_price     = request.args.get('max_price', '')
    status_filter = request.args.get('status', '')
    sort          = request.args.get('sort', 'score')
    order         = request.args.get('order', 'desc')
    try:
        limit  = min(int(request.args.get('limit',  200)), 500)
        offset = max(int(request.args.get('offset', 0)),   0)
    except ValueError:
        return jsonify({'error': 'limit and offset must be integers.'}), 400

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

    sort_col = {
        'score': Whisky.score, 'name': Whisky.name,
        'added': Whisky.created_at, 'price': Whisky.price,
    }.get(sort, Whisky.score)
    if order == 'asc':
        query = query.order_by(sort_col.asc().nullslast())
    else:
        query = query.order_by(sort_col.desc().nullslast())

    total    = query.count()
    whiskies = query.offset(offset).limit(limit).all()
    return jsonify({
        'data':   [_whisky_to_dict(w) for w in whiskies],
        'total':  total,
        'limit':  limit,
        'offset': offset,
    })


# ── Wishlist ──────────────────────────────────────────────────────────────────

@app.route('/api/v1/wishlist')
@api_login_required
def api_wishlist():
    """Return the user's wishlist as a JSON array."""
    items = (Whisky.query
             .filter_by(user_id=current_user.id, wishlist=True)
             .order_by(Whisky.created_at.desc()).all())
    return jsonify({'data': [_whisky_to_dict(w) for w in items]})


@csrf.exempt
@app.route('/api/v1/wishlist', methods=['POST'])
@api_login_required
def api_create_wishlist_item():
    """Create a new wishlist item.

    Request body (JSON):
        {"name": "Ardbeg Uigeadail", "wishlist_notes": "Birthday gift idea"}

    ``name`` is the only required field.
    """
    data = request.get_json(silent=True)
    if not data or not str(data.get('name', '')).strip():
        return jsonify({'error': "'name' is required."}), 400
    w = Whisky(user_id=current_user.id, wishlist=True)
    _fill_whisky_from_json(w, data)
    db.session.add(w)
    db.session.commit()
    return jsonify({'data': _whisky_to_dict(w)}), 201


@csrf.exempt
@app.route('/api/v1/wishlist/<int:wid>', methods=['PUT'])
@api_login_required
def api_update_wishlist_item(wid):
    """Update a wishlist item (partial update — only sent fields are changed)."""
    w = Whisky.query.filter_by(id=wid, user_id=current_user.id, wishlist=True).first()
    if not w:
        return jsonify({'error': 'Wishlist item not found.'}), 404
    data = request.get_json(silent=True) or {}
    _fill_whisky_from_json(w, data)
    db.session.commit()
    return jsonify({'data': _whisky_to_dict(w)})


# ── Whisky CRUD (JSON) ────────────────────────────────────────────────────────

@app.route('/api/v1/whisky/<int:wid>')
@api_login_required
def api_whisky_detail(wid):
    """Return full details for a single whisky."""
    w = Whisky.query.filter_by(id=wid, user_id=current_user.id).first()
    if not w:
        return jsonify({'error': 'Whisky not found.'}), 404
    return jsonify({'data': _whisky_to_dict(w)})


@csrf.exempt
@app.route('/api/v1/whisky', methods=['POST'])
@api_login_required
def api_create_whisky():
    """Create a new collection entry.

    Request body (JSON):
        {"name": "Lagavulin 16", "distillery": "Lagavulin", "score": 9.2, ...}

    ``name`` is the only required field.  All other Whisky fields are optional.
    Photos must be uploaded separately via POST /api/v1/whisky/<id>/photo/<slot>.
    """
    data = request.get_json(silent=True)
    if not data or not str(data.get('name', '')).strip():
        return jsonify({'error': "'name' is required."}), 400
    w = Whisky(user_id=current_user.id, wishlist=False)
    _fill_whisky_from_json(w, data)
    db.session.add(w)
    db.session.commit()
    return jsonify({'data': _whisky_to_dict(w)}), 201


@csrf.exempt
@app.route('/api/v1/whisky/<int:wid>', methods=['PUT'])
@api_login_required
def api_update_whisky(wid):
    """Update an existing collection entry (partial update).

    Only fields present in the JSON body are modified.  To clear an optional
    field send it explicitly as ``null`` — e.g. ``{"score": null}``.
    """
    w = Whisky.query.filter_by(id=wid, user_id=current_user.id, wishlist=False).first()
    if not w:
        return jsonify({'error': 'Whisky not found.'}), 404
    data = request.get_json(silent=True) or {}
    if 'name' in data and not str(data['name']).strip():
        return jsonify({'error': "'name' cannot be empty."}), 400
    _fill_whisky_from_json(w, data)
    db.session.commit()
    return jsonify({'data': _whisky_to_dict(w)})


@csrf.exempt
@app.route('/api/v1/whisky/<int:wid>', methods=['DELETE'])
@api_login_required
def api_delete_whisky(wid):
    """Delete a whisky (collection or wishlist)."""
    w = Whisky.query.filter_by(id=wid, user_id=current_user.id).first()
    if not w:
        return jsonify({'error': 'Whisky not found.'}), 404
    _delete_all_photos(w)
    db.session.delete(w)
    db.session.commit()
    return jsonify({'data': {'deleted': wid}})


# ── Photo management (JSON API) ───────────────────────────────────────────────

@csrf.exempt
@app.route('/api/v1/whisky/<int:wid>/photo/<slot>', methods=['POST'])
@api_login_required
def api_upload_photo(wid, slot):
    """Upload or replace a photo for a whisky.

    Send a multipart/form-data request with a single file field named
    ``photo``.  Accepted formats: jpg, jpeg, png, webp.

    ``slot`` must be one of: front | back | cask | barcode
    """
    if slot not in ('front', 'back', 'cask', 'barcode'):
        return jsonify({'error': "slot must be one of: front, back, cask, barcode"}), 400
    w = Whisky.query.filter_by(id=wid, user_id=current_user.id).first()
    if not w:
        return jsonify({'error': 'Whisky not found.'}), 404

    f = request.files.get('photo')
    if not f or not f.filename:
        return jsonify({'error': "No file uploaded. Send the image as 'photo' field."}), 400
    if not allowed_file(f.filename):
        return jsonify({'error': f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

    saved = save_photo(f, w.id, slot)
    if not saved:
        return jsonify({'error': 'Photo processing failed. Check server logs.'}), 500

    # Hold onto the old filename so we can delete it from disk *after* the DB
    # commit succeeds.  Deleting before commit means a failed commit would lose
    # the old file with no record of the new one.
    old_filename = getattr(w, f'photo_{slot}')
    setattr(w, f'photo_{slot}', saved)
    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        _delete_photo_file(saved)   # clean up the newly-written file
        app.logger.error("DB commit failed during photo upload: %s", exc)
        return jsonify({'error': 'Could not save photo reference. Check server logs.'}), 500
    # Commit succeeded — now safe to remove the old file
    _delete_photo_file(old_filename)
    return jsonify({'data': {
        'slot':      slot,
        'photo_url': url_for('serve_photo', filename=saved, _external=False),
    }})


@csrf.exempt
@app.route('/api/v1/whisky/<int:wid>/photo/<slot>', methods=['DELETE'])
@api_login_required
def api_delete_photo(wid, slot):
    """Remove a photo from a whisky, deleting the file from disk and clearing the DB slot."""
    if slot not in ('front', 'back', 'cask', 'barcode'):
        return jsonify({'error': "slot must be one of: front, back, cask, barcode"}), 400
    w = Whisky.query.filter_by(id=wid, user_id=current_user.id).first()
    if not w:
        return jsonify({'error': 'Whisky not found.'}), 404
    _delete_photo_file(getattr(w, f'photo_{slot}'))
    setattr(w, f'photo_{slot}', None)
    db.session.commit()
    return jsonify({'data': {'slot': slot, 'photo_url': None}})


# ── Error handlers ────────────────────────────────────────────────────────────
@app.errorhandler(403)
def forbidden(e):
    return render_template('403.html'), 403

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(413)
def too_large(e):
    flash('Upload too large. Please use smaller photos (max 64 MB total).', 'error')
    return redirect(request.referrer or url_for('new_whisky'))

# Fix 3: handle expired/missing CSRF tokens with a friendly message instead
# of a raw 400 response.
@app.errorhandler(CSRFError)
def csrf_error(e):
    flash('Your session has expired — please try again.', 'error')
    return redirect(request.referrer or url_for('index'))

# ── Startup ───────────────────────────────────────────────────────────────────
_init_db()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
