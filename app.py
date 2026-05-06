import os
import random
import json
import time
from datetime import datetime, timezone, timedelta, date

from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, send_from_directory, abort
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect, validate_csrf
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'images', 'uploads')
DB_FILE = os.path.join(BASE_DIR, 'instance', 'users.db')
os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
ALLOWED_EXT   = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
SLOT_SYMBOLS  = ['0_hourglass', '0_telephone', '0_diamond', '0_floppy', '0_seven']

GEO_REGIONS = [
    {'id': 1, 'name': 'Западная Европа', 'lat': 50, 'lon': 0},
    {'id': 2, 'name': 'Восточная Европа', 'lat': 55, 'lon': 30},
    {'id': 3, 'name': 'Северная Америка', 'lat': 45, 'lon': -100},
    {'id': 4, 'name': 'Южная Америка', 'lat': -15, 'lon': -60},
    {'id': 5, 'name': 'Северная Африка', 'lat': 25, 'lon': 10},
    {'id': 6, 'name': 'Южная Африка', 'lat': -25, 'lon': 20},
    {'id': 7, 'name': 'Западная Азия', 'lat': 35, 'lon': 45},
    {'id': 8, 'name': 'Юго-Восточная Азия', 'lat': 10, 'lon': 110},
    {'id': 9, 'name': 'Южная Азия', 'lat': 20, 'lon': 80},
    {'id': 10, 'name': 'Австралия и Океания', 'lat': -25, 'lon': 135},
]

GEO_LOCATIONS = [
    {'id': 1, 'name': 'Париж', 'hint': 'Эйфелева башня, круассаны и романтика.', 'lat': 48.8566, 'lon': 2.3522},
    {'id': 2, 'name': 'Нью-Йорк', 'hint': 'Высотки Манхэттена, Центральный парк и Статуя Свободы.', 'lat': 40.7128, 'lon': -74.0060},
    {'id': 3, 'name': 'Каир', 'hint': 'Пирамиды, Нил и древняя египетская история.', 'lat': 30.0444, 'lon': 31.2357},
    {'id': 4, 'name': 'Сидней', 'hint': 'Оперный театр и длинный пляж Бонди.', 'lat': -33.8688, 'lon': 151.2093},
    {'id': 5, 'name': 'Токио', 'hint': 'Неон, суши, метро и храмовые ворота.', 'lat': 35.6895, 'lon': 139.6917},
    {'id': 6, 'name': 'Рио-де-Жанейро', 'hint': 'Статуя Христа-Искупителя и пляж Копакабана.', 'lat': -22.9068, 'lon': -43.1729},
    {'id': 7, 'name': 'Москва', 'hint': 'Красная площадь, Кремль и купола собора Василия Блаженного.', 'lat': 55.7558, 'lon': 37.6173},
    {'id': 8, 'name': 'Лондон', 'hint': 'Биг-Бен, Тауэрский мост и автобусные маршруты.', 'lat': 51.5074, 'lon': -0.1278},
]

DAILY_BONUS_BASE   = 50
DAILY_BONUS_STEP   = 10
ONLINE_WINDOW      = 90  # seconds — how long after last_seen a user is "online"
DUEL_ROUNDS        = 3
SHOP_CATEGORIES = {
    'avatar_frame': {'label': 'Рамки', 'description': 'Оформление вашего аватара в профиле.'},
    'profile_bg':   {'label': 'Фоны профиля', 'description': 'Статичные и анимированные фоны для карточки.'},
    'name_color':   {'label': 'Цвет ника', 'description': 'Сделайте имя заметнее на фоне профиля.'},
}

SHOP_ITEMS = {
    'frame_bronze': {
        'label': 'Рамка бронза',
        'price': 200,
        'field': 'avatar_frame',
        'value': 'bronze',
        'category': 'avatar_frame',
        'preview_class': 'frame-bronze',
        'preview_text': 'Рамка бронза',
    },
    'frame_gold': {
        'label': 'Рамка золото',
        'price': 500,
        'field': 'avatar_frame',
        'value': 'gold',
        'category': 'avatar_frame',
        'preview_class': 'frame-gold',
        'preview_text': 'Рамка золото',
    },
    'frame_diamond': {
        'label': 'Рамка алмаз',
        'price': 900,
        'field': 'avatar_frame',
        'value': 'diamond',
        'category': 'avatar_frame',
        'preview_class': 'frame-diamond',
        'preview_text': 'Рамка алмаз',
    },
    'bg_animated': {
        'label': 'Анимированный фон',
        'price': 250,
        'field': 'profile_bg',
        'value': 'animated',
        'category': 'profile_bg',
        'preview_class': 'animated-bg',
        'preview_text': 'Анимированный фон',
    },
    'color_gold': {
        'label': 'Цвет ника золотой',
        'price': 220,
        'field': 'name_color',
        'value': '#f59e0b',
        'category': 'name_color',
        'preview_color': '#f59e0b',
        'preview_text': 'Горячий золотой цвет',
    },
    'color_blue': {
        'label': 'Цвет ника синий',
        'price': 180,
        'field': 'name_color',
        'value': '#60a5fa',
        'category': 'name_color',
        'preview_color': '#60a5fa',
        'preview_text': 'Спокойный синий цвет',
    },
}
FRAME_COLORS = {
    'bronze': '#d97706',
    'gold':   '#f59e0b',
    'diamond':'#38bdf8',
}

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-change-me-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DB_FILE.replace(chr(92), '/')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['GOOGLE_MAPS_API_KEY'] = os.environ.get('GOOGLE_MAPS_API_KEY', '')
# Disable automatic CSRF checking — we validate HTML forms explicitly below.
# JSON API routes (/spin, /roll_dice, etc.) don't need it.
app.config['WTF_CSRF_CHECK_DEFAULT'] = False

csrf          = CSRFProtect(app)
db            = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# ── Models ────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    id               = db.Column(db.Integer, primary_key=True)
    username         = db.Column(db.String(80), unique=True, nullable=False)
    password         = db.Column(db.String(120), nullable=False)
    coins            = db.Column(db.Integer, default=100)
    casino_spins     = db.Column(db.Integer, default=0)
    dice_rolls       = db.Column(db.Integer, default=0)
    tasks_solved     = db.Column(db.Integer, default=0)
    clicks           = db.Column(db.Integer, default=0)
    description      = db.Column(db.String(200), default='')
    photo            = db.Column(db.String(100), default='default.jpg')
    xp               = db.Column(db.Integer, default=0)
    daily_streak     = db.Column(db.Integer, default=0)
    last_bonus_date  = db.Column(db.Date,    nullable=True)
    last_seen        = db.Column(db.DateTime, nullable=True)
    avatar_frame     = db.Column(db.String(20), default='default')
    profile_bg       = db.Column(db.String(20), default='default')
    name_color       = db.Column(db.String(20), default='')
    purchases        = db.Column(db.Text, default='[]')

    @property
    def is_online(self):
        if self.last_seen is None:
            return False
        now = datetime.now(timezone.utc)
        last = self.last_seen
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return (now - last) < timedelta(seconds=ONLINE_WINDOW)

    @property
    def purchased_items(self):
        try:
            return json.loads(self.purchases or '[]')
        except ValueError:
            return []

    def owns_item(self, item_key):
        return item_key in self.purchased_items

    def add_purchase(self, item_key):
        items = self.purchased_items
        if item_key not in items:
            items.append(item_key)
            self.purchases = json.dumps(items)


class GameEvent(db.Model):
    id      = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    game    = db.Column(db.String(20), nullable=False)
    outcome = db.Column(db.String(12), nullable=False)
    amount  = db.Column(db.Integer,    nullable=False)
    ts      = db.Column(db.DateTime,   nullable=False, default=lambda: datetime.now(timezone.utc))


class Like(db.Model):
    id      = db.Column(db.Integer, primary_key=True)
    from_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    to_id   = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('from_id', 'to_id', name='unique_like'),)


class ChatMessage(db.Model):
    id      = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    text    = db.Column(db.String(250), nullable=False)
    ts      = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class Duel(db.Model):
    id                      = db.Column(db.Integer, primary_key=True)
    challenger_id           = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    target_id               = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    bet                     = db.Column(db.Integer, nullable=False)
    status                  = db.Column(db.String(12), nullable=False, default='pending')
    winner_id               = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    mode                    = db.Column(db.String(20), nullable=True)
    location_id             = db.Column(db.Integer, nullable=True)
    challenger_guess        = db.Column(db.Integer, nullable=True)
    target_guess            = db.Column(db.Integer, nullable=True)
    actual_roll             = db.Column(db.Integer, nullable=True)
    challenger_score        = db.Column(db.Integer, nullable=True)
    target_score            = db.Column(db.Integer, nullable=True)
    challenger_symbols      = db.Column(db.Text,    nullable=True)
    target_symbols          = db.Column(db.Text,    nullable=True)
    current_round           = db.Column(db.Integer, default=1, nullable=False)
    challenger_round_scores = db.Column(db.Text, default='[]')
    target_round_scores     = db.Column(db.Text, default='[]')
    challenger_wins         = db.Column(db.Integer, default=0, nullable=False)
    target_wins             = db.Column(db.Integer, default=0, nullable=False)
    created_at              = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    accepted_at             = db.Column(db.DateTime, nullable=True)
    resolved_at             = db.Column(db.DateTime, nullable=True)

    @property
    def challenger_history(self):
        try: return json.loads(self.challenger_round_scores or '[]')
        except ValueError: return []

    @property
    def target_history(self):
        try: return json.loads(self.target_round_scores or '[]')
        except ValueError: return []


def migrate_database():
    with db.engine.begin() as conn:
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='user';"))
        duel_result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='duel';"))
        if result.fetchone() is None or duel_result.fetchone() is None:
            db.create_all()
            return

        info = conn.execute(text('PRAGMA table_info(user);'))
        columns = {row[1] for row in info}
        migrations = {
            'xp': "INTEGER DEFAULT 0",
            'daily_streak': "INTEGER DEFAULT 0",
            'last_bonus_date': "DATE",
            'last_seen': "DATETIME",
            'avatar_frame': "VARCHAR(20) DEFAULT 'default'",
            'profile_bg': "VARCHAR(20) DEFAULT 'default'",
            'name_color': "VARCHAR(20) DEFAULT ''",
            'purchases': "TEXT DEFAULT '[]'",
        }
        for col, definition in migrations.items():
            if col not in columns:
                conn.execute(text(f'ALTER TABLE user ADD COLUMN {col} {definition}'))

        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='duel';"))
        if result.fetchone() is not None:
            info = conn.execute(text('PRAGMA table_info(duel);'))
            duel_columns = {row[1] for row in info}
            duel_migrations = {
                'mode': 'VARCHAR(20)',
                'location_id': 'INTEGER',
                'challenger_guess': 'INTEGER',
                'target_guess': 'INTEGER',
                'actual_roll': 'INTEGER',
                'challenger_score': 'INTEGER',
                'target_score': 'INTEGER',
                'challenger_symbols': 'TEXT',
                'target_symbols': 'TEXT',
                'current_round': 'INTEGER DEFAULT 1',
                'challenger_round_scores': "TEXT DEFAULT '[]'",
                'target_round_scores': "TEXT DEFAULT '[]'",
                'challenger_wins': 'INTEGER DEFAULT 0',
                'target_wins': 'INTEGER DEFAULT 0',
            }
            for col, definition in duel_migrations.items():
                if col not in duel_columns:
                    conn.execute(text(f'ALTER TABLE duel ADD COLUMN {col} {definition}'))

        db.create_all()


with app.app_context():
    migrate_database()


# ── Helpers ───────────────────────────────────────────────────

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.before_request
def _touch_last_seen():
    """Heartbeat: update current_user.last_seen on every request (throttled)."""
    if not current_user.is_authenticated:
        return
    try:
        now = datetime.now(timezone.utc)
        last = current_user.last_seen
        if last is not None and last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if last is None or (now - last) > timedelta(seconds=20):
            current_user.last_seen = now
            db.session.commit()
    except Exception:
        db.session.rollback()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


def get_achievement_image(count):
    if count >= 5000: return 'dimond.jpg'
    if count >= 2000: return 'izumrud.jpg'
    if count >= 1000: return 'gold.jpg'
    if count >= 500:  return 'silver.jpg'
    if count >= 100:  return 'bronze.jpg'
    return 'no.jpg'


def calculate_slot_winnings(symbols, bet):
    winnings = 0

    # Horizontal: consecutive from left in each row
    row_mult = {3: 2, 4: 5, 5: 20}
    for row in range(3):
        count = 1
        for col in range(1, 5):
            if symbols[col][row] == symbols[col - 1][row]:
                count += 1
            else:
                if count >= 3:
                    winnings += bet * row_mult[min(count, 5)]
                count = 1
        if count >= 3:
            winnings += bet * row_mult[min(count, 5)]

    # Vertical: all 3 rows same in a column
    for col in range(5):
        if symbols[col][0] == symbols[col][1] == symbols[col][2]:
            winnings += bet * 3

    # Diagonal ↘: (sc,0) → (sc+1,1) → (sc+2,2)
    for sc in range(3):
        if symbols[sc][0] == symbols[sc + 1][1] == symbols[sc + 2][2]:
            winnings += bet * 4

    # Diagonal ↙: (sc,0) → (sc-1,1) → (sc-2,2)
    for sc in range(2, 5):
        if symbols[sc][0] == symbols[sc - 1][1] == symbols[sc - 2][2]:
            winnings += bet * 4

    return winnings


def get_like_count(user_id):
    return Like.query.filter_by(to_id=user_id).count()


def has_liked(from_id, to_id):
    return bool(Like.query.filter_by(from_id=from_id, to_id=to_id).first())


def _require_form_csrf():
    """Validate CSRF token submitted with an HTML form or JSON request."""
    token = request.form.get('csrf_token') or request.headers.get('X-CSRFToken')
    try:
        validate_csrf(token)
    except Exception:
        abort(400, 'CSRF validation failed')


def calculate_level(xp):
    return xp // 100 + 1


def xp_to_next_level(xp):
    return 100 - (xp % 100)


def get_profile_theme(user):
    if user.profile_bg == 'animated':
        return 'profile-card animated-bg'
    if user.avatar_frame in FRAME_COLORS:
        return 'profile-card frame-' + user.avatar_frame
    return 'profile-card'


def compute_user_stats(user):
    events = GameEvent.query.filter(GameEvent.user_id == user.id,
                                    GameEvent.game.in_(['slots', 'dice', 'duel'])).order_by(GameEvent.ts.desc()).all()
    total = len(events)
    wins = sum(1 for ev in events if ev.amount > 0)
    losses = sum(1 for ev in events if ev.amount < 0)
    win_rate = round((wins / total) * 100, 1) if total else 0
    biggest = max((ev.amount for ev in events if ev.amount > 0), default=0)
    streak = 0
    for ev in events:
        if ev.amount > 0:
            streak += 1
        else:
            break
    return {
        'total_games': total,
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'best_win': biggest,
        'current_streak': streak,
    }


def distance_km(lat1, lon1, lat2, lon2):
    from math import radians, sin, cos, sqrt, atan2
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c


def get_geo_location(location_id):
    for loc in GEO_LOCATIONS:
        if loc['id'] == location_id:
            return loc
    return None


def get_geo_region(region_id):
    for region in GEO_REGIONS:
        if region['id'] == region_id:
            return region
    return None

app.jinja_env.globals.update(get_geo_region=get_geo_region)


def finish_round(duel):
    """Called when both players submitted score for current round.
    Saves round to history, increments win counter, advances or resolves the duel."""
    c = duel.challenger_score if duel.challenger_score is not None else 0
    t = duel.target_score     if duel.target_score     is not None else 0

    c_hist = duel.challenger_history
    t_hist = duel.target_history
    c_hist.append(c)
    t_hist.append(t)
    duel.challenger_round_scores = json.dumps(c_hist)
    duel.target_round_scores     = json.dumps(t_hist)

    if c > t:
        duel.challenger_wins += 1
    elif t > c:
        duel.target_wins += 1
    # tied round: nobody scores

    if duel.current_round >= DUEL_ROUNDS:
        return resolve_duel_final(duel)
    # advance to next round
    duel.current_round  += 1
    duel.challenger_score   = None
    duel.target_score       = None
    duel.challenger_symbols = None
    duel.target_symbols     = None
    return None


def resolve_duel_final(duel):
    challenger = db.session.get(User, duel.challenger_id)
    target     = db.session.get(User, duel.target_id)
    if challenger is None or target is None:
        return 'Ошибка участников'

    cw, tw = duel.challenger_wins, duel.target_wins
    if cw > tw:
        challenger.coins += duel.bet * 2
        duel.winner_id = challenger.id
        record_game_event(challenger, 'duel', duel.bet,  'win')
        record_game_event(target,     'duel', -duel.bet, 'lose')
        message = f'Победил {challenger.username} ({cw}-{tw})'
    elif tw > cw:
        target.coins += duel.bet * 2
        duel.winner_id = target.id
        record_game_event(target,     'duel', duel.bet,  'win')
        record_game_event(challenger, 'duel', -duel.bet, 'lose')
        message = f'Победил {target.username} ({tw}-{cw})'
    else:
        challenger.coins += duel.bet
        target.coins     += duel.bet
        record_game_event(challenger, 'duel', 0, 'tie')
        record_game_event(target,     'duel', 0, 'tie')
        message = f'Ничья ({cw}-{tw}) — ставки возвращены'
    duel.status = 'resolved'
    duel.resolved_at = datetime.now(timezone.utc)
    return message


def record_game_event(user, game, amount, outcome):
    if game in ('slots', 'dice', 'duel'):
        user.xp += max(5, abs(amount) // 4)
    if game == 'clicker':
        user.xp += max(2, amount)
    if game == 'bonus':
        user.xp += 10
    if game == 'shop':
        user.xp += 5

    db.session.add(GameEvent(
        user_id=user.id,
        game=game,
        outcome=outcome,
        amount=amount,
    ))

# ── PWA ───────────────────────────────────────────────────────

@app.route('/sw.js')
def service_worker():
    return send_from_directory(app.static_folder, 'sw.js',
                               mimetype='application/javascript')


# ── Auth ──────────────────────────────────────────────────────

@app.route('/')
def home():
    return render_template('home.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        _require_form_csrf()
        username = request.form['username'].strip()
        password = request.form['password']
        remember = 'remember' in request.form
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user, remember=remember)
            return redirect(url_for('main_menu'))
        flash('Неверное имя пользователя или пароль')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        _require_form_csrf()
        username  = request.form['username'].strip()
        password  = request.form['password']
        password2 = request.form['password2']

        if not username:
            flash('Имя пользователя не может быть пустым')
            return redirect(url_for('register'))
        if len(password) < 6:
            flash('Пароль должен содержать минимум 6 символов')
            return redirect(url_for('register'))
        if password != password2:
            flash('Пароли не совпадают')
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash('Это имя уже занято')
            return redirect(url_for('register'))

        db.session.add(User(username=username, password=generate_password_hash(password)))
        db.session.commit()
        flash('Регистрация успешна! Войдите в аккаунт.')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из аккаунта')
    return redirect(url_for('home'))


# ── Navigation ────────────────────────────────────────────────

@app.route('/main_menu')
@login_required
def main_menu():
    return render_template('main_menu.html')


@app.route('/daily_bonus', methods=['POST'])
@login_required
def daily_bonus():
    _require_form_csrf()
    today = date.today()
    if current_user.last_bonus_date == today:
        flash('Бонус уже получен сегодня')
        return redirect(url_for('profile'))

    if current_user.last_bonus_date == today - timedelta(days=1):
        current_user.daily_streak += 1
    else:
        current_user.daily_streak = 1

    bonus = DAILY_BONUS_BASE + DAILY_BONUS_STEP * (current_user.daily_streak - 1)
    current_user.coins += bonus
    current_user.last_bonus_date = today
    record_game_event(current_user, 'bonus', bonus, 'bonus')
    db.session.commit()
    flash(f'Ежедневный бонус получен: +{bonus} монет (стрик {current_user.daily_streak} дн.)')
    return redirect(url_for('profile'))


@app.route('/shop', methods=['GET', 'POST'])
@login_required
def shop():
    if request.method == 'POST':
        _require_form_csrf()
        item = request.form.get('item')
        action = request.form.get('action', 'buy')
        payload = SHOP_ITEMS.get(item)
        if payload is None:
            flash('Товар не найден')
            return redirect(url_for('shop'))
        
        if action == 'activate':
            if not current_user.owns_item(item):
                flash('Нельзя активировать некупленный товар')
                return redirect(url_for('shop'))

            setattr(current_user, payload['field'], payload['value'])
            db.session.commit()
            flash(f"Активирован: {payload['label']}")
            return redirect(url_for('shop'))

        if current_user.owns_item(item):
            flash('Товар уже куплен. Переключитесь на него.')
            return redirect(url_for('shop'))

        if current_user.coins < payload['price']:
            flash('Недостаточно монет')
            return redirect(url_for('shop'))

        current_user.coins -= payload['price']
        current_user.add_purchase(item)
        setattr(current_user, payload['field'], payload['value'])
        record_game_event(current_user, 'shop', -payload['price'], 'purchase')
        db.session.commit()
        flash(f"Куплено: {payload['label']}")
        return redirect(url_for('shop'))

    grouped_items = {cat: [] for cat in SHOP_CATEGORIES}
    for key, item in SHOP_ITEMS.items():
        field = item['field']
        value = item['value']
        current_value = getattr(current_user, field, '')
        is_active = current_value == value
        is_owned = current_user.owns_item(key)
        if is_active:
            status = 'active'
        elif is_owned:
            status = 'owned'
        else:
            status = 'not_owned'
        grouped_items[item['category']].append({
            'key': key,
            'status': status,
            **item
        })

    return render_template('shop.html', categories=SHOP_CATEGORIES, grouped_items=grouped_items)


def _msg_to_dict(msg, author):
    return {
        'id':       msg.id,
        'user_id':  msg.user_id,
        'username': author.username if author else 'Неизвестный',
        'color':    (author.name_color if author and author.name_color else ''),
        'level':    (author.xp // 100 + 1) if author else 1,
        'is_online': bool(author and author.is_online),
        'text':     msg.text,
        'ts':       msg.ts.strftime('%d.%m %H:%M'),
        'is_me':    bool(author and author.id == current_user.id),
    }


@app.route('/chat')
@login_required
def chat():
    return render_template('chat.html')


@app.route('/chat/messages')
@login_required
def chat_messages():
    since = request.args.get('since', type=int) or 0
    q = ChatMessage.query
    if since:
        q = q.filter(ChatMessage.id > since).order_by(ChatMessage.id.asc()).limit(50)
    else:
        q = q.order_by(ChatMessage.ts.desc()).limit(50)
    msgs = q.all()
    if not since:
        msgs = msgs[::-1]
    user_ids = [m.user_id for m in msgs]
    users = {u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()} if user_ids else {}
    return jsonify({'messages': [_msg_to_dict(m, users.get(m.user_id)) for m in msgs]})


@app.route('/chat/send', methods=['POST'])
@login_required
def chat_send():
    _require_form_csrf()
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'Пустое сообщение'}), 400
    if len(text) > 240:
        return jsonify({'error': 'Слишком длинное сообщение'}), 400
    msg = ChatMessage(user_id=current_user.id, text=text)
    db.session.add(msg)
    db.session.commit()
    return jsonify({'ok': True, 'message': _msg_to_dict(msg, current_user)})


@app.route('/chat/online')
@login_required
def chat_online():
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=ONLINE_WINDOW)
    users = User.query.filter(User.last_seen.isnot(None)).order_by(User.last_seen.desc()).limit(50).all()
    online = [{
        'id':         u.id,
        'username':   u.username,
        'color':      u.name_color or '',
        'level':      u.xp // 100 + 1,
    } for u in users if u.is_online]
    return jsonify({'users': online, 'count': len(online)})


@app.route('/transfer', methods=['POST'])
@login_required
def transfer():
    _require_form_csrf()
    username = request.form.get('username', '').strip()
    amount = request.form.get('amount', type=int)
    if not username or not amount or amount <= 0:
        flash('Неверные данные для перевода')
        return redirect(url_for('profile'))
    if amount > current_user.coins:
        flash('Недостаточно монет')
        return redirect(url_for('profile'))
    target = User.query.filter_by(username=username).first()
    if target is None:
        flash('Пользователь не найден')
        return redirect(url_for('profile'))
    if target.id == current_user.id:
        flash('Нельзя переводить монеты самому себе')
        return redirect(url_for('profile'))

    current_user.coins -= amount
    target.coins += amount
    record_game_event(current_user, 'transfer', -amount, 'out')
    record_game_event(target, 'transfer', amount, 'in')
    db.session.commit()
    flash(f'Переведено {amount} монет пользователю {target.username}')
    return redirect(url_for('profile'))


@app.route('/duels')
@login_required
def duels():
    incoming = Duel.query.filter_by(target_id=current_user.id, status='pending').order_by(Duel.created_at.desc()).all()
    outgoing = Duel.query.filter_by(challenger_id=current_user.id, status='pending').order_by(Duel.created_at.desc()).all()
    active = Duel.query.filter(
        ((Duel.challenger_id == current_user.id) | (Duel.target_id == current_user.id)),
        Duel.status == 'accepted'
    ).order_by(Duel.accepted_at.desc()).all()
    recent = Duel.query.filter(
        ((Duel.challenger_id == current_user.id) | (Duel.target_id == current_user.id)),
        Duel.status == 'resolved'
    ).order_by(Duel.resolved_at.desc()).limit(20).all()
    user_ids = {d.challenger_id for d in incoming + outgoing + active + recent} | {d.target_id for d in incoming + outgoing + active + recent}
    users = {u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()} if user_ids else {}
    return render_template('duels.html', incoming=incoming, outgoing=outgoing, active=active, recent=recent, users=users)


@app.route('/duel/challenge/<int:user_id>', methods=['POST'])
@login_required
def challenge_user(user_id):
    _require_form_csrf()
    if user_id == current_user.id:
        return jsonify({'error': 'Нельзя вызвать себя'}), 400

    bet = request.form.get('bet', type=int)
    if not bet or bet <= 0:
        return jsonify({'error': 'Неверная ставка'}), 400
    if bet > current_user.coins:
        return jsonify({'error': 'Недостаточно монет'}), 400

    target = db.session.get(User, user_id)
    if target is None:
        return jsonify({'error': 'Игрок не найден'}), 404
    if not target.is_online:
        return jsonify({'error': f'{target.username} сейчас не онлайн'}), 400

    existing = Duel.query.filter(
        Duel.status.in_(['pending', 'accepted']),
        ((Duel.challenger_id == current_user.id) & (Duel.target_id == user_id)) |
        ((Duel.challenger_id == user_id) & (Duel.target_id == current_user.id))
    ).first()
    if existing:
        return jsonify({'error': 'У вас уже есть активная дуэль с этим игроком'}), 400

    current_user.coins -= bet
    duel = Duel(challenger_id=current_user.id, target_id=user_id, bet=bet, mode=None)
    db.session.add(duel)
    db.session.commit()
    return jsonify({'ok': True, 'message': 'Вызов отправлен'})


@app.route('/duel/accept/<int:duel_id>', methods=['POST'])
@login_required
def accept_duel(duel_id):
    _require_form_csrf()
    duel = db.session.get(Duel, duel_id)
    if duel is None or duel.target_id != current_user.id or duel.status != 'pending':
        return jsonify({'error': 'Дуэль не найдена'}), 404
    if current_user.coins < duel.bet:
        return jsonify({'error': 'Недостаточно монет'}), 400

    challenger = db.session.get(User, duel.challenger_id)
    if challenger is None:
        return jsonify({'error': 'Игрок не найден'}), 404
    if not challenger.is_online:
        return jsonify({'error': f'{challenger.username} сейчас не онлайн — нельзя принять'}), 400

    current_user.coins -= duel.bet
    duel.accepted_at = datetime.now(timezone.utc)
    duel.status = 'accepted'
    db.session.commit()
    return jsonify({
        'ok': True,
        'message': 'Дуэль принята. Выберите тип игры.',
        'redirect': url_for('play_duel', duel_id=duel.id),
    })


@app.route('/duel/decline/<int:duel_id>', methods=['POST'])
@login_required
def decline_duel(duel_id):
    _require_form_csrf()
    duel = db.session.get(Duel, duel_id)
    if duel is None or duel.status != 'pending':
        return jsonify({'error': 'Дуэль не найдена'}), 404
    if duel.target_id != current_user.id and duel.challenger_id != current_user.id:
        return jsonify({'error': 'Нет доступа'}), 403

    challenger = db.session.get(User, duel.challenger_id)
    if challenger:
        challenger.coins += duel.bet
    duel.status = 'declined'
    duel.resolved_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({'ok': True, 'message': 'Дуэль отклонена, ставка возвращена'})


@app.route('/duel/<int:duel_id>/choose', methods=['POST'])
@login_required
def choose_duel_mode(duel_id):
    _require_form_csrf()
    duel = db.session.get(Duel, duel_id)
    if duel is None or duel.status != 'accepted':
        return jsonify({'error': 'Дуэль не активна'}), 404
    if current_user.id not in (duel.challenger_id, duel.target_id):
        return jsonify({'error': 'Нет доступа'}), 403
    if duel.mode is not None:
        return jsonify({'error': 'Игра уже выбрана'}), 400

    mode = request.form.get('mode', '').strip()
    if mode not in ('dice', 'slots'):
        return jsonify({'error': 'Выберите кости или слоты'}), 400

    duel.mode = mode
    db.session.commit()
    return jsonify({'ok': True, 'mode': mode})


@app.route('/duel/<int:duel_id>/play', methods=['POST'])
@login_required
def submit_duel_play(duel_id):
    _require_form_csrf()
    duel = db.session.get(Duel, duel_id)
    if duel is None or duel.status != 'accepted' or duel.mode is None:
        return jsonify({'error': 'Дуэль недоступна'}), 404
    if current_user.id not in (duel.challenger_id, duel.target_id):
        return jsonify({'error': 'Нет доступа'}), 403

    is_challenger = current_user.id == duel.challenger_id
    if is_challenger and duel.challenger_score is not None:
        return jsonify({'error': 'Вы уже сыграли'}), 400
    if not is_challenger and duel.target_score is not None:
        return jsonify({'error': 'Вы уже сыграли'}), 400

    if duel.mode == 'dice':
        score = random.randint(1, 6)
        if is_challenger:
            duel.challenger_score = score
        else:
            duel.target_score = score
        result_payload = {'score': score, 'roll': score}
    else:  # slots — server-authoritative
        symbols = [[random.choice(SLOT_SYMBOLS) for _ in range(3)] for _ in range(5)]
        score = calculate_slot_winnings(symbols, duel.bet)
        symbols_json = json.dumps(symbols)
        if is_challenger:
            duel.challenger_score   = score
            duel.challenger_symbols = symbols_json
        else:
            duel.target_score   = score
            duel.target_symbols = symbols_json
        result_payload = {'score': score, 'symbols': symbols}

    round_done   = False
    duel_done    = False
    final        = None
    round_result = None
    if duel.challenger_score is not None and duel.target_score is not None:
        c = duel.challenger_score
        t = duel.target_score
        round_no = duel.current_round
        message  = finish_round(duel)
        round_done   = True
        round_winner = 'challenger' if c > t else 'target' if t > c else 'tie'
        round_result = {
            'round':            round_no,
            'challenger_score': c,
            'target_score':     t,
            'winner':           round_winner,
        }
        if message is not None:
            duel_done = True
            final = {
                'message':          message,
                'winner_id':        duel.winner_id,
                'is_winner':        duel.winner_id == current_user.id,
                'tie':              duel.winner_id is None,
                'challenger_wins':  duel.challenger_wins,
                'target_wins':      duel.target_wins,
            }

    db.session.commit()
    return jsonify({'ok': True, 'result': result_payload,
                    'round_done':  round_done,
                    'round_result': round_result,
                    'done':        duel_done,
                    'final':       final,
                    'current_round': duel.current_round,
                    'challenger_wins': duel.challenger_wins,
                    'target_wins':     duel.target_wins,
                    'new_balance': current_user.coins})


@app.route('/duel/play/<int:duel_id>', methods=['GET'])
@login_required
def play_duel(duel_id):
    duel = db.session.get(Duel, duel_id)
    if duel is None or current_user.id not in (duel.challenger_id, duel.target_id):
        flash('Дуэль не найдена')
        return redirect(url_for('duels'))

    challenger = db.session.get(User, duel.challenger_id)
    target     = db.session.get(User, duel.target_id)

    if duel.status == 'pending':
        flash('Дуэль ещё не принята')
        return redirect(url_for('duels'))

    is_challenger = current_user.id == duel.challenger_id
    my_score      = duel.challenger_score if is_challenger else duel.target_score
    opp_score     = duel.target_score     if is_challenger else duel.challenger_score
    my_played     = my_score is not None
    opp_played    = opp_score is not None

    return render_template('duel_play.html', duel=duel,
                           challenger=challenger, target=target,
                           is_challenger=is_challenger,
                           my_score=my_score,
                           opp_score=opp_score,
                           my_played=my_played,
                           opp_played=opp_played,
                           current_user=current_user)


@app.route('/duel/<int:duel_id>/state')
@login_required
def duel_state(duel_id):
    duel = db.session.get(Duel, duel_id)
    if duel is None or current_user.id not in (duel.challenger_id, duel.target_id):
        return jsonify({'error': 'Не найдено'}), 404
    is_challenger = current_user.id == duel.challenger_id
    return jsonify({
        'status':           duel.status,
        'mode':             duel.mode,
        'current_round':    duel.current_round,
        'total_rounds':     DUEL_ROUNDS,
        'challenger_wins':  duel.challenger_wins,
        'target_wins':      duel.target_wins,
        'challenger_history': duel.challenger_history,
        'target_history':     duel.target_history,
        'my_score':         duel.challenger_score if is_challenger else duel.target_score,
        'opp_score':        duel.target_score     if is_challenger else duel.challenger_score,
        'my_played':        (duel.challenger_score if is_challenger else duel.target_score) is not None,
        'opp_played':       (duel.target_score     if is_challenger else duel.challenger_score) is not None,
        'winner_id':        duel.winner_id,
        'is_winner':        duel.winner_id == current_user.id if duel.winner_id else None,
    })


@app.route('/notifications')
@login_required
def notifications():
    incoming = Duel.query.filter_by(target_id=current_user.id, status='pending').count()
    active_q = Duel.query.filter(
        Duel.status == 'accepted',
        (Duel.challenger_id == current_user.id) | (Duel.target_id == current_user.id)
    ).order_by(Duel.accepted_at.desc()).all()
    return jsonify({
        'incoming':    incoming,
        'active':      len(active_q),
        'active_ids':  [d.id for d in active_q],
    })


@app.route('/games')
@login_required
def games():
    return render_template('games.html')


# ── Casino / Slots ────────────────────────────────────────────

@app.route('/casino')
@login_required
def casino():
    return render_template('casino.html', user=current_user)


@app.route('/spin', methods=['POST'])
@login_required
def spin():
    _require_form_csrf()
    data = request.get_json(force=True, silent=True) or {}
    bet  = data.get('bet')
    if not isinstance(bet, int) or bet <= 0 or bet > current_user.coins:
        return jsonify({'error': 'Неверная ставка'}), 400

    # Server-authoritative: generate the grid here so client can't fabricate wins
    symbols = [[random.choice(SLOT_SYMBOLS) for _ in range(3)] for _ in range(5)]
    winnings = calculate_slot_winnings(symbols, bet)
    net      = winnings - bet

    current_user.coins        -= bet
    current_user.coins        += winnings
    current_user.casino_spins += 1

    record_game_event(current_user, 'slots', net, 'win' if net > 0 else 'lose')
    db.session.commit()
    return jsonify({
        'symbols':     symbols,
        'winnings':    winnings,
        'new_balance': current_user.coins,
    })


# ── Dice ──────────────────────────────────────────────────────

@app.route('/dice')
@login_required
def dice():
    return render_template('dice.html')


@app.route('/roll_dice', methods=['POST'])
@login_required
def roll_dice():
    _require_form_csrf()
    bet    = request.form.get('bet',    type=int)
    target = request.form.get('target', type=int)

    if not bet or bet <= 0 or bet > current_user.coins:
        return jsonify({'error': 'Неверная ставка'}), 400
    if not target or target < 1 or target > 6:
        return jsonify({'error': 'Число должно быть от 1 до 6'}), 400

    result = random.randint(1, 6)
    current_user.coins      -= bet
    current_user.dice_rolls += 1

    if result == target:
        current_user.coins += bet * 2
        outcome = 'win'
        net     = bet
    else:
        outcome = 'lose'
        net     = -bet

    record_game_event(current_user, 'dice', net, outcome)
    db.session.commit()
    return jsonify({'result': outcome, 'dice_result': result, 'coins': current_user.coins})


# ── Clicker ───────────────────────────────────────────────────

@app.route('/clicker')
@login_required
def clicker():
    return render_template('clicker.html', current_user=current_user)


_click_throttle = {}  # user_id -> monotonic timestamp of last click

@app.route('/update_balance', methods=['POST'])
@login_required
def update_balance():
    _require_form_csrf()
    delta = request.form.get('delta', type=int)
    if delta is None or delta <= 0 or delta > 5:
        return jsonify({'error': 'Bad delta'}), 400

    now  = time.monotonic()
    last = _click_throttle.get(current_user.id, 0)
    if now - last < 0.08:  # ≥80 ms between clicks ≈ 12 cps cap
        return jsonify({'error': 'Too fast'}), 429
    _click_throttle[current_user.id] = now

    current_user.coins  += delta
    current_user.clicks += delta
    record_game_event(current_user, 'clicker', delta, 'earn')
    db.session.commit()
    return jsonify({'balance': current_user.coins})


# ── Profile ───────────────────────────────────────────────────

@app.route('/profile/balance_chart')
@login_required
def profile_balance_chart():
    """Cumulative net change per day for the last 14 days (own profile)."""
    user_id = request.args.get('user_id', type=int) or current_user.id
    since   = datetime.now(timezone.utc) - timedelta(days=14)
    events  = GameEvent.query.filter(
        GameEvent.user_id == user_id, GameEvent.ts >= since
    ).order_by(GameEvent.ts.asc()).all()
    by_day = {}
    for e in events:
        ts = e.ts
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        day = ts.date().isoformat()
        by_day[day] = by_day.get(day, 0) + e.amount
    today = datetime.now(timezone.utc).date()
    labels, deltas, cumulative = [], [], []
    running = 0
    for i in range(13, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        labels.append(d[5:])  # MM-DD
        delta = by_day.get(d, 0)
        deltas.append(delta)
        running += delta
        cumulative.append(running)
    return jsonify({'labels': labels, 'deltas': deltas, 'cumulative': cumulative})


@app.route('/profile')
@login_required
def profile():
    game_filter = request.args.get('game', 'all')
    achievements = {
        'casino_spins': get_achievement_image(current_user.casino_spins),
        'dice_rolls':   get_achievement_image(current_user.dice_rolls),
        'clicks':       get_achievement_image(current_user.clicks),
    }

    history_query = GameEvent.query.filter_by(user_id=current_user.id)
    if game_filter != 'all':
        history_query = history_query.filter_by(game=game_filter)
    history = history_query.order_by(GameEvent.ts.desc()).limit(20).all()

    like_count = get_like_count(current_user.id)
    stats = compute_user_stats(current_user)
    level = calculate_level(current_user.xp)
    next_xp = xp_to_next_level(current_user.xp)
    bonus_ready = current_user.last_bonus_date != date.today()
    return render_template('profile.html',
                           user=current_user,
                           achievements=achievements,
                           history=history,
                           like_count=like_count,
                           stats=stats,
                           level=level,
                           next_xp=next_xp,
                           bonus_ready=bonus_ready,
                           game_filter=game_filter)


@app.route('/profile/<int:user_id>')
@login_required
def view_profile(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        flash('Пользователь не найден')
        return redirect(url_for('top'))

    game_filter = request.args.get('game', 'all')
    achievements = {
        'casino_spins': get_achievement_image(user.casino_spins),
        'dice_rolls':   get_achievement_image(user.dice_rolls),
        'clicks':       get_achievement_image(user.clicks),
    }
    history_q = GameEvent.query.filter_by(user_id=user.id)
    if game_filter != 'all':
        history_q = history_q.filter_by(game=game_filter)
    history    = history_q.order_by(GameEvent.ts.desc()).limit(20).all()
    like_count = get_like_count(user.id)
    user_liked = has_liked(current_user.id, user.id)
    stats      = compute_user_stats(user)
    level      = calculate_level(user.xp)
    return render_template('profile_another_user.html',
                           user=user,
                           achievements=achievements,
                           history=history,
                           like_count=like_count,
                           user_liked=user_liked,
                           stats=stats,
                           level=level,
                           game_filter=game_filter)


@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        _require_form_csrf()
        new_username = request.form['username'].strip()
        if not new_username:
            flash('Имя не может быть пустым')
            return redirect(url_for('edit_profile'))

        existing = User.query.filter_by(username=new_username).first()
        if existing and existing.id != current_user.id:
            flash('Это имя уже занято')
            return redirect(url_for('edit_profile'))

        current_user.username    = new_username
        current_user.description = request.form['description']

        file = request.files.get('photo')
        if file and file.filename:
            if not allowed_file(file.filename):
                flash('Недопустимый формат. Разрешены: png, jpg, jpeg, gif, webp')
                return redirect(url_for('edit_profile'))
            try:
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                current_user.photo = filename
            except Exception as exc:
                flash(f'Ошибка загрузки: {exc}')
                return redirect(url_for('edit_profile'))

        db.session.commit()
        flash('Профиль обновлён!')
        return redirect(url_for('profile'))

    return render_template('edit_profile.html', user=current_user)


# ── Leaderboard ───────────────────────────────────────────────

@app.route('/top')
@login_required
def top():
    period = request.args.get('period', 'all')  # 'all' | 'week' | 'day'
    if period == 'week' or period == 'day':
        delta  = timedelta(days=7) if period == 'week' else timedelta(days=1)
        cutoff = datetime.now(timezone.utc) - delta
        rows = db.session.query(
            User,
            db.func.coalesce(db.func.sum(GameEvent.amount), 0).label('period_amount'),
        ).outerjoin(
            GameEvent,
            db.and_(GameEvent.user_id == User.id, GameEvent.ts >= cutoff)
        ).group_by(User.id).order_by(db.text('period_amount DESC, user.coins DESC')).all()
        users = [r[0] for r in rows]
        period_amounts = {r[0].id: int(r[1] or 0) for r in rows}
    else:
        users = User.query.order_by(User.coins.desc()).all()
        period_amounts = {}
    likes     = {u.id: get_like_count(u.id) for u in users}
    liked_ids = {l.to_id for l in Like.query.filter_by(from_id=current_user.id).all()}
    return render_template('top.html',
                           users=users, likes=likes, liked_ids=liked_ids,
                           frame_colors=FRAME_COLORS,
                           period=period, period_amounts=period_amounts)


@app.route('/like/<int:user_id>', methods=['POST'])
@login_required
def like_user(user_id):
    _require_form_csrf()
    if user_id == current_user.id:
        return jsonify({'error': 'Нельзя лайкнуть себя'}), 400

    target = db.session.get(User, user_id)
    if target is None:
        return jsonify({'error': 'Пользователь не найден'}), 404

    existing = Like.query.filter_by(from_id=current_user.id, to_id=user_id).first()
    if existing:
        db.session.delete(existing)
        liked = False
    else:
        db.session.add(Like(from_id=current_user.id, to_id=user_id))
        liked = True

    db.session.commit()
    count = get_like_count(user_id)
    return jsonify({'liked': liked, 'count': count})


# ── Error handlers ────────────────────────────────────────────

@app.errorhandler(404)
def page_not_found(_):
    return render_template('error.html', code=404,
                           title='Страница не найдена',
                           message='Похоже, такой страницы нет. Попробуйте вернуться на главную.'), 404


@app.errorhandler(500)
def internal_error(_):
    db.session.rollback()
    return render_template('error.html', code=500,
                           title='Что-то пошло не так',
                           message='Внутренняя ошибка сервера. Мы уже знаем и работаем над этим.'), 500


@app.errorhandler(403)
def forbidden(_):
    return render_template('error.html', code=403,
                           title='Доступ закрыт',
                           message='У вас нет прав для просмотра этой страницы.'), 403


# ── Entry point ───────────────────────────────────────────────

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    with app.app_context():
        db.create_all()
    app.run(debug=True)
