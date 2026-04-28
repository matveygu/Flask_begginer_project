import os
import random
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

DAILY_BONUS_BASE   = 50
DAILY_BONUS_STEP   = 10
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
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DB_FILE.replace('\\', '/')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
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
    avatar_frame     = db.Column(db.String(20), default='default')
    profile_bg       = db.Column(db.String(20), default='default')
    name_color       = db.Column(db.String(20), default='')


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
    id              = db.Column(db.Integer, primary_key=True)
    challenger_id   = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    target_id       = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    bet             = db.Column(db.Integer, nullable=False)
    status          = db.Column(db.String(12), nullable=False, default='pending')
    winner_id       = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at      = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    accepted_at     = db.Column(db.DateTime, nullable=True)
    resolved_at     = db.Column(db.DateTime, nullable=True)


def migrate_database():
    with db.engine.begin() as conn:
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='user';"))
        if result.fetchone() is None:
            db.create_all()
            return

        info = conn.execute(text('PRAGMA table_info(user);'))
        columns = {row[1] for row in info}
        migrations = {
            'xp': "INTEGER DEFAULT 0",
            'daily_streak': "INTEGER DEFAULT 0",
            'last_bonus_date': "DATE",
            'avatar_frame': "VARCHAR(20) DEFAULT 'default'",
            'profile_bg': "VARCHAR(20) DEFAULT 'default'",
            'name_color': "VARCHAR(20) DEFAULT ''",
        }
        for col, definition in migrations.items():
            if col not in columns:
                conn.execute(text(f'ALTER TABLE user ADD COLUMN {col} {definition}'))

        db.create_all()


with app.app_context():
    migrate_database()


# ── Helpers ───────────────────────────────────────────────────

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


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
            setattr(current_user, payload['field'], payload['value'])
            db.session.commit()
            flash(f"Активирован: {payload['label']}")
            return redirect(url_for('shop'))
        
        if current_user.coins < payload['price']:
            flash('Недостаточно монет')
            return redirect(url_for('shop'))

        current_user.coins -= payload['price']
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
        is_owned = current_value == value
        is_active = current_value == value
        status = 'active' if is_active else ('owned' if is_owned else 'not_owned')
        grouped_items[item['category']].append({
            'key': key,
            'status': status,
            **item
        })

    return render_template('shop.html', categories=SHOP_CATEGORIES, grouped_items=grouped_items)


@app.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():
    if request.method == 'POST':
        _require_form_csrf()
        text = request.form.get('text', '').strip()
        if not text:
            flash('Сообщение не может быть пустым')
            return redirect(url_for('chat'))
        if len(text) > 240:
            flash('Сообщение слишком длинное')
            return redirect(url_for('chat'))
        db.session.add(ChatMessage(user_id=current_user.id, text=text))
        db.session.commit()
        return redirect(url_for('chat'))

    messages = ChatMessage.query.order_by(ChatMessage.ts.desc()).limit(50).all()[::-1]
    users = {u.id: u for u in User.query.filter(User.id.in_([m.user_id for m in messages])).all()} if messages else {}
    return render_template('chat.html', messages=messages, users=users)


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
    recent = Duel.query.filter(
        ((Duel.challenger_id == current_user.id) | (Duel.target_id == current_user.id)),
        Duel.status == 'resolved'
    ).order_by(Duel.resolved_at.desc()).limit(20).all()
    user_ids = {d.challenger_id for d in incoming + outgoing + recent} | {d.target_id for d in incoming + outgoing + recent}
    users = {u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()} if user_ids else {}
    return render_template('duels.html', incoming=incoming, outgoing=outgoing, recent=recent, users=users)


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

    current_user.coins -= bet
    duel = Duel(challenger_id=current_user.id, target_id=user_id, bet=bet)
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

    current_user.coins -= duel.bet
    challenger_roll = random.randint(1, 6)
    target_roll = random.randint(1, 6)
    duel.accepted_at = datetime.now(timezone.utc)
    duel.resolved_at = datetime.now(timezone.utc)

    if challenger_roll > target_roll:
        challenger.coins += duel.bet * 2
        duel.winner_id = challenger.id
        record_game_event(challenger, 'duel', duel.bet, 'win')
        record_game_event(current_user, 'duel', -duel.bet, 'lose')
        message = 'Победил челленджер'
    elif challenger_roll < target_roll:
        current_user.coins += duel.bet * 2
        duel.winner_id = current_user.id
        record_game_event(current_user, 'duel', duel.bet, 'win')
        record_game_event(challenger, 'duel', -duel.bet, 'lose')
        message = 'Победил принявший вызов'
    else:
        challenger.coins += duel.bet
        current_user.coins += duel.bet
        record_game_event(current_user, 'duel', 0, 'tie')
        record_game_event(challenger, 'duel', 0, 'tie')
        message = 'Ничья — ставки возвращены'

    duel.status = 'resolved'
    db.session.commit()
    return jsonify({
        'ok': True,
        'message': message,
        'challenger_roll': challenger_roll,
        'target_roll': target_roll,
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
    data    = request.get_json(force=True, silent=True) or {}
    bet     = data.get('bet')
    symbols = data.get('symbols')

    if not isinstance(bet, int) or bet <= 0 or bet > current_user.coins:
        return jsonify({'error': 'Неверная ставка'}), 400

    if (not isinstance(symbols, list) or len(symbols) != 5 or
            not all(isinstance(col, list) and len(col) == 3 and
                    all(s in SLOT_SYMBOLS for s in col)
                    for col in symbols)):
        return jsonify({'error': 'Неверные символы'}), 400

    winnings = calculate_slot_winnings(symbols, bet)
    net      = winnings - bet

    current_user.coins        -= bet
    current_user.coins        += winnings
    current_user.casino_spins += 1

    record_game_event(current_user, 'slots', net, 'win' if net > 0 else 'lose')
    db.session.commit()
    return jsonify({'winnings': winnings, 'new_balance': current_user.coins})


# ── Dice ──────────────────────────────────────────────────────

@app.route('/dice')
@login_required
def dice():
    return render_template('dice.html')


@app.route('/roll_dice', methods=['POST'])
@login_required
def roll_dice():
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


@app.route('/update_balance', methods=['POST'])
@login_required
def update_balance():
    delta = request.form.get('delta', type=int)
    if delta is None or delta <= 0 or delta > 50:
        return jsonify({'error': 'Bad delta'}), 400
    current_user.coins  += delta
    current_user.clicks += delta
    record_game_event(current_user, 'clicker', delta, 'earn')
    db.session.commit()
    return jsonify({'balance': current_user.coins})


# ── Profile ───────────────────────────────────────────────────

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

    achievements = {
        'casino_spins': get_achievement_image(user.casino_spins),
        'dice_rolls':   get_achievement_image(user.dice_rolls),
        'clicks':       get_achievement_image(user.clicks),
    }
    history    = GameEvent.query.filter_by(user_id=user.id)\
                     .order_by(GameEvent.ts.desc()).limit(10).all()
    like_count = get_like_count(user.id)
    user_liked = has_liked(current_user.id, user.id)
    return render_template('profile_another_user.html',
                           user=user,
                           achievements=achievements,
                           history=history,
                           like_count=like_count,
                           user_liked=user_liked)


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
    users     = User.query.order_by(User.coins.desc()).all()
    likes     = {u.id: get_like_count(u.id) for u in users}
    liked_ids = {l.to_id for l in Like.query.filter_by(from_id=current_user.id).all()}
    return render_template('top.html', users=users, likes=likes, liked_ids=liked_ids, frame_colors=FRAME_COLORS)


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


# ── Entry point ───────────────────────────────────────────────

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    with app.app_context():
        db.create_all()
    app.run(debug=True)
