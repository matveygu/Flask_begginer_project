import os
import random
from datetime import datetime, timezone

from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, send_from_directory, abort
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect, validate_csrf
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


UPLOAD_FOLDER = 'static/images/uploads'
ALLOWED_EXT   = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
SLOT_SYMBOLS  = ['0_hourglass', '0_telephone', '0_diamond', '0_floppy', '0_seven']

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-change-me-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
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
    id           = db.Column(db.Integer, primary_key=True)
    username     = db.Column(db.String(80), unique=True, nullable=False)
    password     = db.Column(db.String(120), nullable=False)
    coins        = db.Column(db.Integer, default=100)
    casino_spins = db.Column(db.Integer, default=0)
    dice_rolls   = db.Column(db.Integer, default=0)
    tasks_solved = db.Column(db.Integer, default=0)
    clicks       = db.Column(db.Integer, default=0)
    description  = db.Column(db.String(200), default='')
    photo        = db.Column(db.String(100), default='default.jpg')


class GameEvent(db.Model):
    id      = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    game    = db.Column(db.String(10), nullable=False)
    outcome = db.Column(db.String(6),  nullable=False)
    amount  = db.Column(db.Integer,    nullable=False)
    ts      = db.Column(db.DateTime,   nullable=False, default=lambda: datetime.now(timezone.utc))


class Like(db.Model):
    id      = db.Column(db.Integer, primary_key=True)
    from_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    to_id   = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('from_id', 'to_id', name='unique_like'),)


with app.app_context():
    db.create_all()


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
    """Validate CSRF token submitted with an HTML form."""
    try:
        validate_csrf(request.form.get('csrf_token'))
    except Exception:
        abort(400, 'CSRF validation failed')


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

    db.session.add(GameEvent(
        user_id=current_user.id,
        game='slots',
        outcome='win' if net > 0 else 'lose',
        amount=net,
    ))
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

    db.session.add(GameEvent(
        user_id=current_user.id,
        game='dice',
        outcome=outcome,
        amount=net,
    ))
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
    db.session.commit()
    return jsonify({'balance': current_user.coins})


# ── Profile ───────────────────────────────────────────────────

@app.route('/profile')
@login_required
def profile():
    achievements = {
        'casino_spins': get_achievement_image(current_user.casino_spins),
        'dice_rolls':   get_achievement_image(current_user.dice_rolls),
        'clicks':       get_achievement_image(current_user.clicks),
    }
    history    = GameEvent.query.filter_by(user_id=current_user.id)\
                     .order_by(GameEvent.ts.desc()).limit(10).all()
    like_count = get_like_count(current_user.id)
    return render_template('profile.html',
                           user=current_user,
                           achievements=achievements,
                           history=history,
                           like_count=like_count)


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
    return render_template('top.html', users=users, likes=likes, liked_ids=liked_ids)


@app.route('/like/<int:user_id>', methods=['POST'])
@login_required
def like_user(user_id):
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
