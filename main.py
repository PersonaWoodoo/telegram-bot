import asyncio
import random
import sqlite3
import json
import string
import time
import os
from datetime import datetime
from functools import wraps

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    PreCheckoutQuery,
    LabeledPrice,
)

# ========== КОНФИГ ==========
BOT_TOKEN = "8629137165:AAGN-d3ur1qJYiCmGB16HBgSjvcdZMPDK_A"
BOT_NAME = "WILLD GRAMM"
BOT_USERNAME = "WILLDGRAMMbot"
ADMIN_IDS = [8293927811, 8478884644]

# Обязательные подписки
REQUIRED_CHANNEL_ID = -1003877871687
REQUIRED_CHAT_ID = -1003841895912

# Валюты
GRAM_NAME = "💎 Грам"
GOLD_NAME = "🏅 Iris-Gold"

# Стартовые балансы
START_GRAM = 500.0
START_GOLD = 0.0

# Курс Stars (1 Star = 0.70 Gold)
STAR_TO_GOLD = 0.70

# Лимиты
MIN_BET_GRAM = 0.10
MAX_BET_GRAM = 100000.0
MIN_BET_GOLD = 0.01
MAX_BET_GOLD = 5000.0
MIN_WITHDRAW_GRAM = 75000.0
MIN_WITHDRAW_GOLD = 10.0

# Минимальная сумма перевода
MIN_TRANSFER_GRAM = 1.0
MIN_TRANSFER_GOLD = 0.1

# Бонус
BONUS_GRAM_MIN = 0
BONUS_GRAM_MAX = 250

# КД на игры (секунды)
GAME_COOLDOWN = 3

# Хранилище для КД игр
game_cooldown = {}

def can_play_game(user_id: int, game_name: str) -> bool:
    key = f"{user_id}_{game_name}"
    now = time.time()
    if key in game_cooldown:
        if now - game_cooldown[key] < GAME_COOLDOWN:
            return False
    game_cooldown[key] = now
    return True

# ========== МНОЖИТЕЛИ ИГР ==========
FOOTBALL_MULTIPLIERS = {"gol": 1.4, "mimo": 1.6}
BASKET_MULTIPLIERS = {"tochniy": 1.4, "promah": 1.6}
CUBE_MULTIPLIERS = {"normal": 1.8, "three": 2.0}
DICE_MULTIPLIER = 3.5

# ========== БАШНЯ (TOWER) ==========
TOWER_ROWS = 9
TOWER_COLS = 5

def get_tower_multiplier(level: int, mines: int) -> float:
    if level <= 0:
        return 1.0
    safe_cells = 5 - mines
    if safe_cells <= 0:
        return 999.0
    p_safe = safe_cells / 5
    mult = (1.0 / (p_safe ** level)) * 0.97
    return round(min(mult, 50.0), 2)

def create_tower_bombs(levels: int, mines_per_row: int) -> list:
    bombs = []
    for _ in range(levels):
        row = [0] * 5
        positions = random.sample(range(5), mines_per_row)
        for pos in positions:
            row[pos] = 1
        bombs.append(row)
    return bombs

# ========== ЗОЛОТО ==========
def create_gold_path() -> list:
    path = []
    for _ in range(12):
        bomb_side = random.randint(0, 1)
        path.append(bomb_side)
    return path

def get_gold_multiplier(level: int) -> float:
    if level <= 0:
        return 1.0
    return 2.0 ** level

# ========== АЛМАЗЫ ==========
def create_diamond_field() -> int:
    return random.randint(0, 2)

def get_diamond_multiplier() -> float:
    return 2.0

# ========== ФУТБОЛ, БАСКЕТБОЛ, КУБИК, КОСТИ ==========
def football_play(choice: str):
    value = random.randint(1, 6)
    win = (choice == "gol" and value >= 4) or (choice == "mimo" and value <= 3)
    mult = FOOTBALL_MULTIPLIERS["gol"] if (choice == "gol" and win) else FOOTBALL_MULTIPLIERS["mimo"] if win else 0
    return win, mult, value

def basket_play(choice: str):
    value = random.randint(1, 6)
    win = (choice == "tochniy" and value in [4,5]) or (choice == "promah" and value not in [4,5])
    mult = BASKET_MULTIPLIERS["tochniy"] if (choice == "tochniy" and win) else BASKET_MULTIPLIERS["promah"] if win else 0
    return win, mult, value

def cube_play(guess: int):
    value = random.randint(1, 6)
    win = guess == value
    mult = CUBE_MULTIPLIERS["three"] if guess == 3 else CUBE_MULTIPLIERS["normal"]
    return win, mult, value

def dice_play(choice: str):
    d1 = random.randint(1, 6)
    d2 = random.randint(1, 6)
    total = d1 + d2
    win = False
    if choice == "больше" and total > 7:
        win = True
    elif choice == "меньше" and total < 7:
        win = True
    elif choice == "ровно" and total == 7:
        win = True
    return win, DICE_MULTIPLIER, d1, d2, total

# ========== СОЗДАЁМ DP ==========
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ========== БАЗА ДАННЫХ (СОХРАНЯЕТСЯ В ПАПКЕ БОТА) ==========
DB_PATH = "casino.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            gram REAL DEFAULT 500,
            gold REAL DEFAULT 0,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            total_bets INTEGER DEFAULT 0,
            total_wins INTEGER DEFAULT 0,
            last_bonus INTEGER DEFAULT 0,
            total_deposited_gram REAL DEFAULT 0,
            total_deposited_gold REAL DEFAULT 0,
            total_deposited_stars INTEGER DEFAULT 0,
            total_withdrawn_gram REAL DEFAULT 0,
            total_withdrawn_gold REAL DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0,
            registered_at INTEGER DEFAULT 0,
            last_seen INTEGER DEFAULT 0,
            referrer_id TEXT,
            referral_count INTEGER DEFAULT 0,
            referral_earned REAL DEFAULT 0
        )
    ''')
    
    cur.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cur.fetchall()]
    if "gram" not in columns: cur.execute("ALTER TABLE users ADD COLUMN gram REAL DEFAULT 500")
    if "gold" not in columns: cur.execute("ALTER TABLE users ADD COLUMN gold REAL DEFAULT 0")
    if "username" not in columns: cur.execute("ALTER TABLE users ADD COLUMN username TEXT")
    if "first_name" not in columns: cur.execute("ALTER TABLE users ADD COLUMN first_name TEXT")
    if "last_name" not in columns: cur.execute("ALTER TABLE users ADD COLUMN last_name TEXT")
    if "total_bets" not in columns: cur.execute("ALTER TABLE users ADD COLUMN total_bets INTEGER DEFAULT 0")
    if "total_wins" not in columns: cur.execute("ALTER TABLE users ADD COLUMN total_wins INTEGER DEFAULT 0")
    if "last_bonus" not in columns: cur.execute("ALTER TABLE users ADD COLUMN last_bonus INTEGER DEFAULT 0")
    if "total_deposited_gram" not in columns: cur.execute("ALTER TABLE users ADD COLUMN total_deposited_gram REAL DEFAULT 0")
    if "total_deposited_gold" not in columns: cur.execute("ALTER TABLE users ADD COLUMN total_deposited_gold REAL DEFAULT 0")
    if "total_deposited_stars" not in columns: cur.execute("ALTER TABLE users ADD COLUMN total_deposited_stars INTEGER DEFAULT 0")
    if "total_withdrawn_gram" not in columns: cur.execute("ALTER TABLE users ADD COLUMN total_withdrawn_gram REAL DEFAULT 0")
    if "total_withdrawn_gold" not in columns: cur.execute("ALTER TABLE users ADD COLUMN total_withdrawn_gold REAL DEFAULT 0")
    if "is_banned" not in columns: cur.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0")
    if "is_admin" not in columns: cur.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
    if "registered_at" not in columns: cur.execute("ALTER TABLE users ADD COLUMN registered_at INTEGER DEFAULT 0")
    if "last_seen" not in columns: cur.execute("ALTER TABLE users ADD COLUMN last_seen INTEGER DEFAULT 0")
    if "referrer_id" not in columns: cur.execute("ALTER TABLE users ADD COLUMN referrer_id TEXT")
    if "referral_count" not in columns: cur.execute("ALTER TABLE users ADD COLUMN referral_count INTEGER DEFAULT 0")
    if "referral_earned" not in columns: cur.execute("ALTER TABLE users ADD COLUMN referral_earned REAL DEFAULT 0")
    
    for admin_id in ADMIN_IDS:
        cur.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (str(admin_id),))
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS withdraw_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            currency TEXT,
            amount REAL,
            recipient TEXT,
            status TEXT,
            created_at INTEGER,
            processed_at INTEGER
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS deposit_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            currency TEXT,
            amount REAL,
            screenshot_id TEXT,
            status TEXT,
            created_at INTEGER,
            processed_at INTEGER
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS transfer_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user TEXT,
            to_user TEXT,
            currency TEXT,
            amount REAL,
            timestamp INTEGER
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS checks (
            code TEXT PRIMARY KEY,
            creator_id TEXT,
            per_user REAL,
            currency TEXT,
            remaining INTEGER,
            claimed TEXT
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS promos (
            name TEXT PRIMARY KEY,
            reward_gram REAL,
            reward_gold REAL,
            remaining_activations INTEGER,
            claimed TEXT
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id TEXT,
            action TEXT,
            target_id TEXT,
            amount REAL,
            timestamp INTEGER
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('star_to_gold', ?)", (str(STAR_TO_GOLD),))
    
    conn.commit()
    conn.close()
    print(f"✅ База данных инициализирована: {DB_PATH}")

init_db()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def now_ts():
    return int(time.time())

def fmt_gram(value: float) -> str:
    value = round(value, 2)
    if value >= 1000:
        return f"{value/1000:.1f}K {GRAM_NAME}"
    return f"{value:.2f} {GRAM_NAME}"

def fmt_gold(value: float) -> str:
    value = round(value, 2)
    if value >= 1000:
        return f"{value/1000:.1f}K {GOLD_NAME}"
    return f"{value:.2f} {GOLD_NAME}"

def fmt_money(currency: str, value: float) -> str:
    return fmt_gram(value) if currency == "gram" else fmt_gold(value)

def escape_html(text: str) -> str:
    return str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def mention_user(user_id: int, name: str = None) -> str:
    name = escape_html(name or f"Игрок{user_id}")
    return f'<a href="tg://user?id={user_id}">{name}</a>'

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def is_banned(user_id: int) -> bool:
    conn = get_db()
    row = conn.execute("SELECT is_banned FROM users WHERE user_id = ?", (str(user_id),)).fetchone()
    conn.close()
    return row and row["is_banned"] == 1

def ensure_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None, referrer_id: int = None):
    conn = get_db()
    existing = conn.execute("SELECT * FROM users WHERE user_id = ?", (str(user_id),)).fetchone()
    
    if not existing:
        conn.execute("""
            INSERT INTO users (user_id, gram, gold, is_admin, registered_at, username, first_name, last_name, referrer_id) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (str(user_id), START_GRAM, START_GOLD, 1 if user_id in ADMIN_IDS else 0, now_ts(), username, first_name, last_name, str(referrer_id) if referrer_id else None))
        
        if referrer_id and referrer_id != user_id:
            update_balance(referrer_id, "gram", 1500)
            conn.execute("UPDATE users SET referral_count = referral_count + 1, referral_earned = referral_earned + 1500 WHERE user_id = ?", (str(referrer_id),))
            conn.commit()
    else:
        conn.execute("UPDATE users SET username = ?, first_name = ?, last_name = ?, last_seen = ? WHERE user_id = ?", 
                     (username, first_name, last_name, now_ts(), str(user_id)))
    
    conn.commit()
    conn.close()

def update_user_info(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    conn = get_db()
    if username:
        conn.execute("UPDATE users SET username = ?, last_seen = ? WHERE user_id = ?", (username, now_ts(), str(user_id)))
    if first_name:
        conn.execute("UPDATE users SET first_name = ?, last_seen = ? WHERE user_id = ?", (first_name, now_ts(), str(user_id)))
    if last_name:
        conn.execute("UPDATE users SET last_name = ?, last_seen = ? WHERE user_id = ?", (last_name, now_ts(), str(user_id)))
    conn.execute("UPDATE users SET last_seen = ? WHERE user_id = ?", (now_ts(), str(user_id)))
    conn.commit()
    conn.close()

def get_user(user_id: int):
    conn = get_db()
    ensure_user(user_id)
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (str(user_id),)).fetchone()
    conn.close()
    return row

def get_user_by_username(username: str):
    conn = get_db()
    username = username.lstrip('@')
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return row

def get_star_to_gold_rate() -> float:
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key = 'star_to_gold'").fetchone()
    conn.close()
    return float(row["value"]) if row else 0.70

def set_star_to_gold_rate(rate: float):
    conn = get_db()
    conn.execute("UPDATE settings SET value = ? WHERE key = 'star_to_gold'", (str(rate),))
    conn.commit()
    conn.close()

def update_balance(user_id: int, currency: str, delta: float) -> float:
    conn = get_db()
    conn.execute(f"UPDATE users SET {currency} = {currency} + ? WHERE user_id = ?", 
                 (round(delta, 2), str(user_id)))
    conn.commit()
    row = conn.execute(f"SELECT {currency} FROM users WHERE user_id = ?", (str(user_id),)).fetchone()
    conn.close()
    return row[currency]

def add_transfer_history(from_user: int, to_user: int, currency: str, amount: float):
    conn = get_db()
    conn.execute('''
        INSERT INTO transfer_history (from_user, to_user, currency, amount, timestamp)
        VALUES (?, ?, ?, ?, ?)
    ''', (str(from_user), str(to_user), currency, amount, now_ts()))
    conn.commit()
    conn.close()

def add_admin_log(admin_id: int, action: str, target_id: int = None, amount: float = None):
    conn = get_db()
    conn.execute("INSERT INTO admin_logs (admin_id, action, target_id, amount, timestamp) VALUES (?, ?, ?, ?, ?)",
                 (str(admin_id), action, str(target_id) if target_id else None, amount, now_ts()))
    conn.commit()
    conn.close()

def add_bet_record(user_id: int, bet: float, win: bool, game: str, currency: str):
    conn = get_db()
    conn.execute("UPDATE users SET total_bets = total_bets + 1 WHERE user_id = ?", (str(user_id),))
    if win:
        conn.execute("UPDATE users SET total_wins = total_wins + 1 WHERE user_id = ?", (str(user_id),))
    conn.commit()
    conn.close()
    
    if not win:
        user = get_user(user_id)
        if user and user["referrer_id"]:
            referrer_id = int(user["referrer_id"])
            if referrer_id:
                ref_bonus = bet * 0.01
                update_balance(referrer_id, "gram", ref_bonus)
                conn = get_db()
                conn.execute("UPDATE users SET referral_earned = referral_earned + ? WHERE user_id = ?", (ref_bonus, str(referrer_id)))
                conn.commit()
                conn.close()

def get_top_players(currency: str, limit: int = 10):
    conn = get_db()
    rows = conn.execute(f"SELECT user_id, username, {currency} FROM users WHERE is_banned = 0 ORDER BY {currency} DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return rows

def get_all_users():
    conn = get_db()
    rows = conn.execute("SELECT user_id, gram, gold, is_admin, is_banned, username, first_name, registered_at FROM users ORDER BY user_id").fetchall()
    conn.close()
    return rows

def get_admin_logs(limit: int = 50):
    conn = get_db()
    rows = conn.execute("SELECT * FROM admin_logs ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return rows

def get_bot_stats():
    conn = get_db()
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_bets = conn.execute("SELECT SUM(total_bets) FROM users").fetchone()[0] or 0
    total_wins = conn.execute("SELECT SUM(total_wins) FROM users").fetchone()[0] or 0
    total_deposited_gram = conn.execute("SELECT SUM(total_deposited_gram) FROM users").fetchone()[0] or 0
    total_deposited_gold = conn.execute("SELECT SUM(total_deposited_gold) FROM users").fetchone()[0] or 0
    total_deposited_stars = conn.execute("SELECT SUM(total_deposited_stars) FROM users").fetchone()[0] or 0
    total_withdrawn_gram = conn.execute("SELECT SUM(total_withdrawn_gram) FROM users").fetchone()[0] or 0
    total_withdrawn_gold = conn.execute("SELECT SUM(total_withdrawn_gold) FROM users").fetchone()[0] or 0
    conn.close()
    return {
        "total_users": total_users,
        "total_bets": total_bets,
        "total_wins": total_wins,
        "total_deposited_gram": total_deposited_gram,
        "total_deposited_gold": total_deposited_gold,
        "total_deposited_stars": total_deposited_stars,
        "total_withdrawn_gram": total_withdrawn_gram,
        "total_withdrawn_gold": total_withdrawn_gold,
    }

def reset_all_balances():
    conn = get_db()
    conn.execute("UPDATE users SET gram = 500, gold = 0")
    conn.commit()
    conn.close()

# ========== ЗАЯВКИ ==========
def create_deposit_request(user_id: int, currency: str, amount: float, screenshot_id: str) -> int:
    conn = get_db()
    conn.execute('''
        INSERT INTO deposit_requests (user_id, currency, amount, screenshot_id, status, created_at)
        VALUES (?, ?, ?, ?, 'pending', ?)
    ''', (str(user_id), currency, amount, screenshot_id, now_ts()))
    conn.commit()
    req_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return req_id

def approve_deposit(req_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM deposit_requests WHERE id = ?", (req_id,)).fetchone()
    if not row:
        conn.close()
        return False
    user_id = row["user_id"]
    currency = row["currency"]
    amount = row["amount"]
    update_balance(int(user_id), currency, amount)
    if currency == "gram":
        conn.execute("UPDATE users SET total_deposited_gram = total_deposited_gram + ? WHERE user_id = ?", (amount, user_id))
    else:
        conn.execute("UPDATE users SET total_deposited_gold = total_deposited_gold + ? WHERE user_id = ?", (amount, user_id))
    conn.execute("UPDATE deposit_requests SET status = 'approved', processed_at = ? WHERE id = ?", (now_ts(), req_id))
    conn.commit()
    conn.close()
    return True

def decline_deposit(req_id: int):
    conn = get_db()
    conn.execute("UPDATE deposit_requests SET status = 'declined', processed_at = ? WHERE id = ?", (now_ts(), req_id))
    conn.commit()
    conn.close()
    return True

def get_pending_deposits():
    conn = get_db()
    rows = conn.execute("SELECT * FROM deposit_requests WHERE status = 'pending' ORDER BY created_at ASC").fetchall()
    conn.close()
    return rows

def create_withdraw_request(user_id: int, currency: str, amount: float, recipient: str) -> int:
    conn = get_db()
    conn.execute('''
        INSERT INTO withdraw_requests (user_id, currency, amount, recipient, status, created_at)
        VALUES (?, ?, ?, ?, 'pending', ?)
    ''', (str(user_id), currency, amount, recipient, now_ts()))
    conn.commit()
    req_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return req_id

def approve_withdraw(req_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM withdraw_requests WHERE id = ?", (req_id,)).fetchone()
    if not row:
        conn.close()
        return False
    user_id = row["user_id"]
    currency = row["currency"]
    amount = row["amount"]
    update_balance(int(user_id), currency, -amount)
    if currency == "gram":
        conn.execute("UPDATE users SET total_withdrawn_gram = total_withdrawn_gram + ? WHERE user_id = ?", (amount, user_id))
    else:
        conn.execute("UPDATE users SET total_withdrawn_gold = total_withdrawn_gold + ? WHERE user_id = ?", (amount, user_id))
    conn.execute("UPDATE withdraw_requests SET status = 'approved', processed_at = ? WHERE id = ?", (now_ts(), req_id))
    conn.commit()
    conn.close()
    return True

def decline_withdraw(req_id: int):
    conn = get_db()
    conn.execute("UPDATE withdraw_requests SET status = 'declined', processed_at = ? WHERE id = ?", (now_ts(), req_id))
    conn.commit()
    conn.close()
    return True

def get_pending_withdraws():
    conn = get_db()
    rows = conn.execute("SELECT * FROM withdraw_requests WHERE status = 'pending' ORDER BY created_at ASC").fetchall()
    conn.close()
    return rows

# ========== ЧЕКИ ==========
def generate_check_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def create_check(user_id: int, amount: float, currency: str, count: int):
    total = amount * count
    user = get_user(user_id)
    if user[currency] < total:
        return False, "❌ Недостаточно средств!"
    update_balance(user_id, currency, -total)
    code = generate_check_code()
    conn = get_db()
    conn.execute("INSERT INTO checks (code, creator_id, per_user, currency, remaining, claimed) VALUES (?, ?, ?, ?, ?, ?)",
                 (code, str(user_id), amount, currency, count, "[]"))
    conn.commit()
    conn.close()
    return True, code

def claim_check(user_id: int, code: str):
    conn = get_db()
    row = conn.execute("SELECT * FROM checks WHERE code = ?", (code.upper(),)).fetchone()
    if not row:
        conn.close()
        return False, "❌ Чек не найден!", 0, ""
    if row["remaining"] <= 0:
        conn.close()
        return False, "❌ Чек уже использован!", 0, ""
    claimed = json.loads(row["claimed"])
    if str(user_id) in claimed:
        conn.close()
        return False, "❌ Вы уже активировали этот чек!", 0, ""
    claimed.append(str(user_id))
    reward = row["per_user"]
    currency = row["currency"]
    update_balance(user_id, currency, reward)
    conn.execute("UPDATE checks SET remaining = remaining - 1, claimed = ? WHERE code = ?",
                 (json.dumps(claimed), code.upper()))
    conn.commit()
    conn.close()
    return True, f"✅ Чек активирован! +{fmt_money(currency, reward)}", reward, currency

def get_user_checks(user_id: int):
    conn = get_db()
    rows = conn.execute("SELECT code, per_user, currency, remaining FROM checks WHERE creator_id = ?", (str(user_id),)).fetchall()
    conn.close()
    return rows

# ========== ПРОМОКОДЫ ==========
def create_promo(code: str, reward_gram: float, reward_gold: float, activations: int):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO promos (name, reward_gram, reward_gold, remaining_activations, claimed) VALUES (?, ?, ?, ?, ?)",
                 (code.upper(), reward_gram, reward_gold, activations, "[]"))
    conn.commit()
    conn.close()

def redeem_promo(user_id: int, code: str):
    conn = get_db()
    row = conn.execute("SELECT * FROM promos WHERE name = ?", (code.upper(),)).fetchone()
    if not row:
        conn.close()
        return False, "❌ Промокод не найден!", 0, 0
    if row["remaining_activations"] <= 0:
        conn.close()
        return False, "❌ Промокод уже использован!", 0, 0
    claimed = json.loads(row["claimed"])
    if str(user_id) in claimed:
        conn.close()
        return False, "❌ Вы уже активировали этот промокод!", 0, 0
    claimed.append(str(user_id))
    reward_gram = row["reward_gram"] or 0
    reward_gold = row["reward_gold"] or 0
    if reward_gram > 0:
        update_balance(user_id, "gram", reward_gram)
    if reward_gold > 0:
        update_balance(user_id, "gold", reward_gold)
    conn.execute("UPDATE promos SET remaining_activations = remaining_activations - 1, claimed = ? WHERE name = ?",
                 (json.dumps(claimed), code.upper()))
    conn.commit()
    conn.close()
    return True, "✅ Промокод активирован!", reward_gram, reward_gold

# ========== ПРОВЕРКА ПОДПИСКИ ==========
async def check_subscription_by_id(user_id: int, bot: Bot, chat_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ["member", "creator", "administrator"]
    except:
        return False

async def check_all_subscriptions(user_id: int, bot: Bot):
    is_channel = await check_subscription_by_id(user_id, bot, REQUIRED_CHANNEL_ID)
    is_chat = await check_subscription_by_id(user_id, bot, REQUIRED_CHAT_ID)
    return is_channel, is_chat

def get_subscribe_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться на канал", url="https://t.me/WILLDGRAMM")],
        [InlineKeyboardButton(text="💬 Подписаться на чат", url="https://t.me/willdgrammchat")],
        [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_subscribe")]
    ])

# ========== INLINE КЛАВИАТУРЫ ==========
def main_menu():
    kb = [
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile"), InlineKeyboardButton(text="🎮 Игры", callback_data="games")],
        [InlineKeyboardButton(text="💎 Пополнить", callback_data="deposit"), InlineKeyboardButton(text="💰 Вывести", callback_data="withdraw")],
        [InlineKeyboardButton(text="🎁 Бонус", callback_data="bonus"), InlineKeyboardButton(text="🏆 Топ", callback_data="top")],
        [InlineKeyboardButton(text="🔄 Перевести", callback_data="transfer_menu"), InlineKeyboardButton(text="🫶 Рефералы", callback_data="ref")],
        [InlineKeyboardButton(text="🧾 Чеки", callback_data="checks_menu"), InlineKeyboardButton(text="🎟 Промокод", callback_data="promo_menu")]
    ]
    if is_admin(ADMIN_IDS[0]):
        kb.append([InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def transfer_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Перевести Граммы", callback_data="transfer_gram")],
        [InlineKeyboardButton(text="🏅 Перевести Iris-Gold", callback_data="transfer_gold")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

def games_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🥇 Золото", callback_data="game_gold"), InlineKeyboardButton(text="💎 Алмазы", callback_data="game_diamond")],
        [InlineKeyboardButton(text="🗼 Башня", callback_data="game_tower"), InlineKeyboardButton(text="🎲 Кубик", callback_data="game_cube")],
        [InlineKeyboardButton(text="🎯 Кости", callback_data="game_dice"), InlineKeyboardButton(text="⚽ Футбол", callback_data="game_football")],
        [InlineKeyboardButton(text="🏀 Баскетбол", callback_data="game_basket"), InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

def admin_panel_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Все пользователи", callback_data="admin_all_users")],
        [InlineKeyboardButton(text="💰 Выдать валюту", callback_data="admin_give"), InlineKeyboardButton(text="🔫 Забрать валюту", callback_data="admin_take")],
        [InlineKeyboardButton(text="👑 Выдать админа", callback_data="admin_set_admin"), InlineKeyboardButton(text="👑 Снять админа", callback_data="admin_remove_admin")],
        [InlineKeyboardButton(text="🔒 Заблокировать", callback_data="admin_ban"), InlineKeyboardButton(text="🔓 Разблокировать", callback_data="admin_unban")],
        [InlineKeyboardButton(text="🗑 Обнулить балансы", callback_data="admin_reset_balances")],
        [InlineKeyboardButton(text="💱 Изменить курс Stars", callback_data="admin_set_rate")],
        [InlineKeyboardButton(text="📥 Заявки на вывод", callback_data="admin_withdraw_requests"), InlineKeyboardButton(text="📤 Заявки на пополнение", callback_data="admin_deposit_requests")],
        [InlineKeyboardButton(text="📊 Статистика бота", callback_data="admin_stats"), InlineKeyboardButton(text="📜 Логи админов", callback_data="admin_logs")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"), InlineKeyboardButton(text="🎟 Создать промокод", callback_data="admin_create_promo")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

def deposit_currency_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Пополнить Stars (мгновенно)", callback_data="deposit_stars")],
        [InlineKeyboardButton(text="💎 Пополнить Граммы (заявка)", callback_data="deposit_gram")],
        [InlineKeyboardButton(text="🏅 Пополнить Iris-Gold (заявка)", callback_data="deposit_gold")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

def stars_amount_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ 1 Star", callback_data="stars_1"), InlineKeyboardButton(text="⭐ 5 Stars", callback_data="stars_5")],
        [InlineKeyboardButton(text="⭐ 10 Stars", callback_data="stars_10"), InlineKeyboardButton(text="⭐ 20 Stars", callback_data="stars_20")],
        [InlineKeyboardButton(text="⭐ 50 Stars", callback_data="stars_50"), InlineKeyboardButton(text="⭐ 100 Stars", callback_data="stars_100")],
        [InlineKeyboardButton(text="✏️ Своя сумма", callback_data="stars_custom")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="deposit")]
    ])

def withdraw_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Вывести Граммы", callback_data="withdraw_gram")],
        [InlineKeyboardButton(text="🏅 Вывести Iris-Gold", callback_data="withdraw_gold")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

def checks_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать чек", callback_data="check_create")],
        [InlineKeyboardButton(text="💸 Активировать чек", callback_data="check_claim")],
        [InlineKeyboardButton(text="📋 Мои чеки", callback_data="check_my")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

def back_button():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]])

# ========== СОСТОЯНИЯ ==========
class GameStates(StatesGroup):
    waiting_bet_amount = State()
    waiting_currency = State()
    waiting_tower_mines = State()
    waiting_tower_choice = State()
    waiting_gold_choice = State()
    waiting_diamond_choice = State()

class DepositStates(StatesGroup):
    waiting_custom_stars = State()
    waiting_gram_amount = State()
    waiting_gram_screenshot = State()
    waiting_gold_amount = State()
    waiting_gold_screenshot = State()

class WithdrawStates(StatesGroup):
    waiting_currency = State()
    waiting_amount = State()
    waiting_recipient = State()

class TransferStates(StatesGroup):
    waiting_currency = State()
    waiting_amount = State()
    waiting_recipient = State()

class CheckStates(StatesGroup):
    waiting_amount = State()
    waiting_count = State()
    waiting_currency = State()
    waiting_code = State()

class PromoStates(StatesGroup):
    waiting_code = State()

class AdminStates(StatesGroup):
    waiting_user_id = State()
    waiting_amount = State()
    waiting_currency = State()
    waiting_broadcast = State()
    waiting_promo_code = State()
    waiting_promo_reward_gram = State()
    waiting_promo_reward_gold = State()
    waiting_promo_activations = State()
    waiting_new_rate = State()

# ========== ХРАНИЛИЩА АКТИВНЫХ ИГР ==========
active_games = {}
active_tower_games = {}
active_gold_games = {}
active_diamond_games = {}

# ========== ОСНОВНЫЕ ОБРАБОТЧИКИ ==========
@dp.message(CommandStart())
async def start_cmd(message: Message, bot: Bot):
    if is_banned(message.from_user.id):
        await message.answer("❌ Вы забанены и не можете использовать бота!")
        return
    
    referrer_id = None
    if len(message.text.split()) > 1:
        try:
            referrer_id = int(message.text.split()[1])
            if referrer_id == message.from_user.id:
                referrer_id = None
        except:
            pass
    
    update_user_info(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name
    )
    
    ensure_user(message.from_user.id, message.from_user.username, message.from_user.first_name, message.from_user.last_name, referrer_id)
    
    is_channel, is_chat = await check_all_subscriptions(message.from_user.id, bot)
    
    if not is_channel or not is_chat:
        text = "🔒 <b>Доступ ограничен</b>\n\nТы ещё не подписан на:\n"
        if not is_channel: text += "❌ <b>Канал:</b> @WILLDGRAMM\n"
        if not is_chat: text += "❌ <b>Чат:</b> @willdgrammchat\n"
        text += "\nПодпишись и нажми проверку!"
        await message.answer(text, reply_markup=get_subscribe_keyboard())
        return
    
    user = get_user(message.from_user.id)
    star_rate = get_star_to_gold_rate()
    await message.answer(
        f"🌟 <b>Добро пожаловать в {BOT_NAME}!</b>\n\n"
        f"💰 <b>Твой баланс:</b>\n"
        f"💎 {GRAM_NAME}: {fmt_gram(user['gram'])}\n"
        f"🏅 {GOLD_NAME}: {fmt_gold(user['gold'])}\n\n"
        f"⭐ <b>Курс Stars:</b> 1 Star = {fmt_gold(star_rate)}\n\n"
        f"👇 Используй кнопки ниже:",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "check_subscribe")
async def check_subscribe_callback(call: CallbackQuery, bot: Bot):
    is_channel, is_chat = await check_all_subscriptions(call.from_user.id, bot)
    if is_channel and is_chat:
        await call.message.edit_text("✅ Подписка подтверждена! Теперь вы можете пользоваться ботом.", reply_markup=None)
        user = get_user(call.from_user.id)
        star_rate = get_star_to_gold_rate()
        await call.message.answer(
            f"🌟 <b>Добро пожаловать в {BOT_NAME}!</b>\n\n"
            f"💰 Баланс:\n💎 {fmt_gram(user['gram'])}\n🏅 {fmt_gold(user['gold'])}\n\n"
            f"⭐ Курс Stars: 1 Star = {fmt_gold(star_rate)}",
            reply_markup=main_menu()
        )
    else:
        text = "🔒 Доступ ограничен. Вы не подписаны:\n"
        if not is_channel: text += "❌ Канал @WILLDGRAMM\n"
        if not is_chat: text += "❌ Чат @willdgrammchat\n"
        text += "\nПодпишитесь и нажмите проверку."
        await call.message.edit_text(text, reply_markup=get_subscribe_keyboard())
    await call.answer()

@dp.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery, bot: Bot):
    if is_banned(call.from_user.id):
        await call.message.answer("❌ Вы забанены!")
        return
    is_channel, is_chat = await check_all_subscriptions(call.from_user.id, bot)
    if not is_channel or not is_chat:
        await start_cmd(call.message, bot)
        return
    user = get_user(call.from_user.id)
    await call.message.edit_text(
        f"🌟 Главное меню\n\n💰 Баланс:\n💎 {fmt_gram(user['gram'])}\n🏅 {fmt_gold(user['gold'])}",
        reply_markup=main_menu()
    )
    await call.answer()

# ========== ПРОФИЛЬ, ТОП, БОНУС, РЕФЕРАЛЫ ==========
@dp.callback_query(F.data == "profile")
async def profile_cmd(call: CallbackQuery):
    if is_banned(call.from_user.id):
        await call.answer("❌ Вы забанены!", show_alert=True)
        return
    user = get_user(call.from_user.id)
    wins = user["total_wins"] or 0
    bets = user["total_bets"] or 1
    wr = (wins / bets) * 100
    admin_status = "👑 Администратор" if user["is_admin"] else "👤 Пользователь"
    star_rate = get_star_to_gold_rate()
    await call.message.edit_text(
        f"👤 <b>Профиль</b>\n\n"
        f"🆔 ID: <code>{call.from_user.id}</code>\n"
        f"📊 Статус: {admin_status}\n\n"
        f"💰 Баланс:\n💎 {fmt_gram(user['gram'])}\n🏅 {fmt_gold(user['gold'])}\n\n"
        f"📊 Статистика:\n"
        f"💎 Пополнено: {fmt_gram(user['total_deposited_gram'] or 0)}\n"
        f"🏅 Пополнено: {fmt_gold(user['total_deposited_gold'] or 0)}\n"
        f"⭐ Пополнено Stars: {user['total_deposited_stars'] or 0}\n"
        f"📤 Выведено: {fmt_gram(user['total_withdrawn_gram'] or 0)} / {fmt_gold(user['total_withdrawn_gold'] or 0)}\n"
        f"🎲 Ставок: {bets} | Побед: {wins} ({wr:.1f}%)\n\n"
        f"⭐ Курс Stars: 1 Star = {fmt_gold(star_rate)}\n\n"
        f"📊 Лимиты:\n💎 {fmt_gram(MIN_BET_GRAM)}-{fmt_gram(MAX_BET_GRAM)} | 🏅 {fmt_gold(MIN_BET_GOLD)}-{fmt_gold(MAX_BET_GOLD)}\n"
        f"💎 Мин. вывод: {fmt_gram(MIN_WITHDRAW_GRAM)}\n🏅 Мин. вывод: {fmt_gold(MIN_WITHDRAW_GOLD)}",
        reply_markup=back_button()
    )
    await call.answer()

@dp.callback_query(F.data == "top")
async def top_cmd(call: CallbackQuery):
    top_gram = get_top_players("gram", 5)
    top_gold = get_top_players("gold", 5)
    medals = ["🥇", "🥈", "🥉"]
    text = "🏆 <b>Топ игроков</b>\n\n💎 <b>Граммы:</b>\n"
    for i, p in enumerate(top_gram):
        medal = medals[i] if i < 3 else f"{i+1}."
        name = p["username"] or f"ID{p['user_id']}"
        text += f"{medal} @{name} — {fmt_gram(p['gram'])}\n"
    text += "\n🏅 <b>Iris-Gold:</b>\n"
    for i, p in enumerate(top_gold):
        medal = medals[i] if i < 3 else f"{i+1}."
        name = p["username"] or f"ID{p['user_id']}"
        text += f"{medal} @{name} — {fmt_gold(p['gold'])}\n"
    await call.message.edit_text(text, reply_markup=back_button())
    await call.answer()

@dp.callback_query(F.data == "bonus")
async def bonus_cmd(call: CallbackQuery):
    if is_banned(call.from_user.id):
        await call.answer("❌ Вы забанены!", show_alert=True)
        return
    user_id = call.from_user.id
    user = get_user(user_id)
    last = user["last_bonus"] or 0
    now = now_ts()
    if now - last < 43200:
        left = 43200 - (now - last)
        h = left // 3600
        m = (left % 3600) // 60
        await call.message.edit_text(f"⏰ Бонус через {h}ч {m}мин", reply_markup=back_button())
        await call.answer()
        return
    reward = random.randint(BONUS_GRAM_MIN, BONUS_GRAM_MAX)
    update_balance(user_id, "gram", reward)
    conn = get_db()
    conn.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?", (now, str(user_id)))
    conn.commit()
    conn.close()
    await call.message.edit_text(f"🎁 Ежедневный бонус!\n💎 +{fmt_gram(reward)}", reply_markup=back_button())
    await call.answer()

@dp.callback_query(F.data == "ref")
async def ref_cmd(call: CallbackQuery):
    if is_banned(call.from_user.id):
        await call.answer("❌ Вы забанены!", show_alert=True)
        return
    
    user = get_user(call.from_user.id)
    ref_link = f"https://t.me/{BOT_USERNAME}?start={call.from_user.id}"
    
    text = (
        f"🫶 <b>{mention_user(call.from_user.id, call.from_user.first_name)}</b>, зарабатывай, приглашая друзей:\n\n"
        f"💰 Баланс: {fmt_gram(user['gram'])}\n"
        f"💸 Всего заработано: {fmt_gram(user['referral_earned'] or 0)}\n"
        f"🧲 Приглашено друзей: {user['referral_count'] or 0}\n\n"
        f"🔗 <b>Твоя реферальная ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"🎁 <b>Что ты получаешь:</b>\n"
        f"• 🤑 1500 {GRAM_NAME} — за регистрацию друга\n"
        f"• 💎 5% — с каждого доната друга\n"
        f"• 💰 1% — с каждого проигрыша друга"
    )
    
    await call.message.edit_text(text, reply_markup=back_button())
    await call.answer()

# ========== ПЕРЕВОДЫ МЕЖДУ ИГРОКАМИ ==========
@dp.callback_query(F.data == "transfer_menu")
async def transfer_menu_cmd(call: CallbackQuery):
    if is_banned(call.from_user.id):
        await call.answer("❌ Вы забанены!", show_alert=True)
        return
    await call.message.edit_text("🔄 <b>Перевод валюты</b>\n\nВыберите валюту для перевода:", reply_markup=transfer_menu())
    await call.answer()

@dp.callback_query(F.data == "transfer_gram")
async def transfer_gram_start(call: CallbackQuery, state: FSMContext):
    if is_banned(call.from_user.id):
        await call.answer("❌ Вы забанены!", show_alert=True)
        return
    await state.update_data(currency="gram")
    await state.set_state(TransferStates.waiting_amount)
    await call.message.edit_text(
        f"💎 <b>Перевод {GRAM_NAME}</b>\n\n"
        f"💰 Введите сумму перевода (мин. {fmt_gram(MIN_TRANSFER_GRAM)}):\n"
        f"📊 Ваш баланс: {fmt_gram(get_user(call.from_user.id)['gram'])}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="transfer_menu")]])
    )
    await call.answer()

@dp.callback_query(F.data == "transfer_gold")
async def transfer_gold_start(call: CallbackQuery, state: FSMContext):
    if is_banned(call.from_user.id):
        await call.answer("❌ Вы забанены!", show_alert=True)
        return
    await state.update_data(currency="gold")
    await state.set_state(TransferStates.waiting_amount)
    await call.message.edit_text(
        f"🏅 <b>Перевод {GOLD_NAME}</b>\n\n"
        f"💰 Введите сумму перевода (мин. {fmt_gold(MIN_TRANSFER_GOLD)}):\n"
        f"📊 Ваш баланс: {fmt_gold(get_user(call.from_user.id)['gold'])}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="transfer_menu")]])
    )
    await call.answer()

@dp.message(TransferStates.waiting_amount)
async def transfer_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        data = await state.get_data()
        currency = data["currency"]
        
        min_amount = MIN_TRANSFER_GRAM if currency == "gram" else MIN_TRANSFER_GOLD
        
        if amount < min_amount:
            await message.answer(f"❌ Минимальная сумма перевода: {fmt_money(currency, min_amount)}")
            return
        
        user = get_user(message.from_user.id)
        if user[currency] < amount:
            await message.answer(f"❌ Недостаточно средств. Ваш баланс: {fmt_money(currency, user[currency])}")
            return
        
        await state.update_data(amount=amount)
        await state.set_state(TransferStates.waiting_recipient)
        await message.answer(
            f"📝 <b>Кому перевести?</b>\n\n"
            f"💰 Сумма: {fmt_money(currency, amount)}\n\n"
            f"Введите @username или ID получателя:"
        )
    except:
        await message.answer("❌ Введите корректную сумму!")

@dp.message(TransferStates.waiting_recipient)
async def transfer_recipient(message: Message, state: FSMContext):
    recipient_input = message.text.strip()
    data = await state.get_data()
    currency = data["currency"]
    amount = data["amount"]
    
    recipient = None
    if recipient_input.startswith("@"):
        user_data = get_user_by_username(recipient_input)
        if user_data:
            recipient = int(user_data["user_id"])
    elif recipient_input.isdigit():
        recipient = int(recipient_input)
    
    if not recipient:
        await message.answer("❌ Пользователь не найден! Проверьте @username или ID.")
        return
    
    if recipient == message.from_user.id:
        await message.answer("❌ Нельзя перевести средства самому себе!")
        return
    
    if is_banned(recipient):
        await message.answer("❌ Получатель забанен и не может принимать переводы!")
        return
    
    update_balance(message.from_user.id, currency, -amount)
    update_balance(recipient, currency, amount)
    add_transfer_history(message.from_user.id, recipient, currency, amount)
    
    sender_name = mention_user(message.from_user.id, message.from_user.first_name)
    recipient_name = mention_user(recipient, get_user(recipient)["first_name"] or str(recipient))
    
    await message.answer(
        f"✅ <b>Перевод выполнен!</b>\n\n"
        f"👤 Отправитель: {sender_name}\n"
        f"👤 Получатель: {recipient_name}\n"
        f"💰 Сумма: {fmt_money(currency, amount)}\n"
        f"💎 Ваш новый баланс: {fmt_money(currency, get_user(message.from_user.id)[currency])}",
        reply_markup=main_menu()
    )
    
    try:
        await message.bot.send_message(
            recipient,
            f"✅ <b>Вам поступил перевод!</b>\n\n"
            f"👤 От: {sender_name}\n"
            f"💰 Сумма: {fmt_money(currency, amount)}\n"
            f"💎 Новый баланс: {fmt_money(currency, get_user(recipient)[currency])}"
        )
    except:
        pass
    
    await state.clear()

# ========== ИГРЫ (INLINE) ==========
@dp.callback_query(F.data == "games")
async def games_list(call: CallbackQuery):
    if is_banned(call.from_user.id):
        await call.answer("❌ Вы забанены!", show_alert=True)
        return
    await call.message.edit_text("🎮 <b>Выбери игру</b>\n\n⏰ КД на игры: 3 секунды", reply_markup=games_menu())
    await call.answer()

# ---------- ЗОЛОТО ----------
@dp.callback_query(F.data == "game_gold")
async def gold_start(call: CallbackQuery, state: FSMContext):
    if is_banned(call.from_user.id):
        await call.answer("❌ Вы забанены!", show_alert=True)
        return
    
    if not can_play_game(call.from_user.id, "gold"):
        await call.answer("⏰ Подожди 3 секунды перед следующей игрой в Золото!", show_alert=True)
        return
    
    if call.from_user.id in active_gold_games:
        await call.answer("❌ У вас уже есть активная игра в Золото!", show_alert=True)
        return
    
    await state.set_state(GameStates.waiting_currency)
    await state.update_data(game="gold")
    await call.message.edit_text(
        "🥇 <b>Игра Золото</b>\n\n"
        "Выбери валюту для ставки:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Граммы", callback_data="gold_curr_gram")],
            [InlineKeyboardButton(text="🏅 Iris-Gold", callback_data="gold_curr_gold")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="games")]
        ])
    )
    await call.answer()

@dp.callback_query(F.data.startswith("gold_curr_"))
async def gold_set_currency(call: CallbackQuery, state: FSMContext):
    currency = call.data.split("_")[2]
    await state.update_data(currency=currency)
    await state.set_state(GameStates.waiting_bet_amount)
    await call.message.edit_text(
        f"🥇 <b>Игра Золото</b>\n\n"
        f"💰 Введи сумму ставки в {GRAM_NAME if currency == 'gram' else GOLD_NAME}\n"
        f"📊 Лимиты: от {fmt_money(currency, MIN_BET_GRAM if currency == 'gram' else MIN_BET_GOLD)} до {fmt_money(currency, MAX_BET_GRAM if currency == 'gram' else MAX_BET_GOLD)}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="games")]])
    )
    await call.answer()

@dp.message(GameStates.waiting_bet_amount)
async def gold_process_bet(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("game") != "gold":
        return
    
    try:
        bet = float(message.text.replace(",", "."))
        currency = data["currency"]
        
        min_bet = MIN_BET_GRAM if currency == "gram" else MIN_BET_GOLD
        max_bet = MAX_BET_GRAM if currency == "gram" else MAX_BET_GOLD
        
        if bet < min_bet or bet > max_bet:
            await message.answer(f"❌ Ставка должна быть от {fmt_money(currency, min_bet)} до {fmt_money(currency, max_bet)}")
            return
        
        user = get_user(message.from_user.id)
        if user[currency] < bet:
            await message.answer(f"❌ Недостаточно средств. Баланс: {fmt_money(currency, user[currency])}")
            return
        
        path = create_gold_path()
        active_gold_games[message.from_user.id] = {
            "bet": bet,
            "currency": currency,
            "path": path,
            "level": 0,
            "user_id": message.from_user.id
        }
        
        await state.clear()
        await show_gold_game(message, message.from_user.id)
        
    except:
        await message.answer("❌ Введи корректную сумму!")

async def show_gold_game(message: Message, user_id: int):
    game = active_gold_games.get(user_id)
    if not game:
        return
    
    level = game["level"]
    bet = game["bet"]
    currency = game["currency"]
    path = game["path"]
    
    current_mult = get_gold_multiplier(level)
    current_win = bet * current_mult
    next_mult = get_gold_multiplier(level + 1)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Левая клетка", callback_data=f"gold_choice_left"), InlineKeyboardButton(text="Правая клетка ▶️", callback_data=f"gold_choice_right")],
        [InlineKeyboardButton(text="💰 Забрать выигрыш", callback_data="gold_cashout")],
        [InlineKeyboardButton(text="❌ Закончить игру", callback_data="gold_cancel")]
    ])
    
    text = (
        f"🥇 <b>Игра Золото</b>\n\n"
        f"💰 Ставка: {fmt_money(currency, bet)}\n"
        f"🏆 Уровень: {level}/12\n"
        f"📈 Текущий множитель: x{current_mult:.2f}\n"
        f"💸 Потенциальный выигрыш сейчас: {fmt_money(currency, current_win)}\n"
        f"🎯 Следующий множитель: x{next_mult:.2f}\n\n"
        f"Выбери клетку (левая или правая):"
    )
    
    await message.answer(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("gold_choice_"))
async def gold_make_choice(call: CallbackQuery):
    user_id = call.from_user.id
    game = active_gold_games.get(user_id)
    if not game:
        await call.answer("❌ Игра не найдена! Начните заново.", show_alert=True)
        return
    
    choice = call.data.split("_")[2]
    choice_num = 0 if choice == "left" else 1
    
    level = game["level"]
    path = game["path"]
    
    if level >= len(path):
        await call.answer("❌ Игра уже завершена!", show_alert=True)
        return
    
    bomb_side = path[level]
    
    if choice_num == bomb_side:
        bet = game["bet"]
        currency = game["currency"]
        update_balance(user_id, currency, -bet)
        add_bet_record(user_id, bet, False, "gold", currency)
        
        del active_gold_games[user_id]
        
        await call.message.edit_text(
            f"💥 <b>Игра Золото</b>\n\n"
            f"❌ Ты попал на мину на {level + 1} уровне!\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"📊 Результат: <b>ПРОИГРЫШ 😔</b>",
            reply_markup=games_menu()
        )
    else:
        game["level"] += 1
        new_level = game["level"]
        
        if new_level >= len(path):
            bet = game["bet"]
            currency = game["currency"]
            payout = bet * get_gold_multiplier(new_level)
            update_balance(user_id, currency, -bet + payout)
            add_bet_record(user_id, bet, True, "gold", currency)
            
            del active_gold_games[user_id]
            
            await call.message.edit_text(
                f"🏆 <b>Игра Золото</b>\n\n"
                f"🎉 Ты прошёл все 12 уровней!\n"
                f"💰 Ставка: {fmt_money(currency, bet)}\n"
                f"💸 Выплата: {fmt_money(currency, payout)}\n"
                f"📊 Результат: <b>ПОБЕДА 🎉</b>",
                reply_markup=games_menu()
            )
        else:
            await show_gold_game(call.message, user_id)
            await call.answer("✅ Ты выбрал безопасную клетку! Продолжай!")
    
    await call.answer()

@dp.callback_query(F.data == "gold_cashout")
async def gold_cashout(call: CallbackQuery):
    user_id = call.from_user.id
    game = active_gold_games.get(user_id)
    if not game:
        await call.answer("❌ Игра не найдена!", show_alert=True)
        return
    
    level = game["level"]
    if level == 0:
        await call.answer("❌ Сначала сделай хотя бы 1 ход!", show_alert=True)
        return
    
    bet = game["bet"]
    currency = game["currency"]
    mult = get_gold_multiplier(level)
    payout = bet * mult
    
    update_balance(user_id, currency, -bet + payout)
    add_bet_record(user_id, bet, True, "gold", currency)
    
    del active_gold_games[user_id]
    
    await call.message.edit_text(
        f"💰 <b>Игра Золото</b>\n\n"
        f"✅ Ты забрал выигрыш на {level} уровне!\n"
        f"💰 Ставка: {fmt_money(currency, bet)}\n"
        f"💸 Выплата: {fmt_money(currency, payout)}\n"
        f"📊 Результат: <b>ПОБЕДА 🎉</b>",
        reply_markup=games_menu()
    )
    await call.answer()

@dp.callback_query(F.data == "gold_cancel")
async def gold_cancel(call: CallbackQuery):
    user_id = call.from_user.id
    game = active_gold_games.get(user_id)
    if not game:
        await call.answer("❌ Игра не найдена!", show_alert=True)
        return
    
    level = game["level"]
    bet = game["bet"]
    currency = game["currency"]
    
    if level == 0:
        update_balance(user_id, currency, bet)
        await call.message.edit_text(
            f"❌ <b>Игра Золото отменена</b>\n\n"
            f"💰 Ставка возвращена: {fmt_money(currency, bet)}",
            reply_markup=games_menu()
        )
    else:
        await call.message.edit_text(
            f"❌ <b>Игра Золото завершена</b>\n\n"
            f"💰 Ставка не возвращается, так как ты сделал ход(ы).",
            reply_markup=games_menu()
        )
    
    del active_gold_games[user_id]
    await call.answer()

# ---------- АЛМАЗЫ ----------
@dp.callback_query(F.data == "game_diamond")
async def diamond_start(call: CallbackQuery, state: FSMContext):
    if is_banned(call.from_user.id):
        await call.answer("❌ Вы забанены!", show_alert=True)
        return
    
    if not can_play_game(call.from_user.id, "diamond"):
        await call.answer("⏰ Подожди 3 секунды перед следующей игрой в Алмазы!", show_alert=True)
        return
    
    if call.from_user.id in active_diamond_games:
        await call.answer("❌ У вас уже есть активная игра в Алмазы!", show_alert=True)
        return
    
    await state.set_state(GameStates.waiting_currency)
    await state.update_data(game="diamond")
    await call.message.edit_text(
        "💎 <b>Игра Алмазы</b>\n\n"
        "Выбери валюту для ставки:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Граммы", callback_data="diamond_curr_gram")],
            [InlineKeyboardButton(text="🏅 Iris-Gold", callback_data="diamond_curr_gold")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="games")]
        ])
    )
    await call.answer()

@dp.callback_query(F.data.startswith("diamond_curr_"))
async def diamond_set_currency(call: CallbackQuery, state: FSMContext):
    currency = call.data.split("_")[2]
    await state.update_data(currency=currency)
    await state.set_state(GameStates.waiting_bet_amount)
    await call.message.edit_text(
        f"💎 <b>Игра Алмазы</b>\n\n"
        f"💰 Введи сумму ставки в {GRAM_NAME if currency == 'gram' else GOLD_NAME}\n"
        f"📊 Лимиты: от {fmt_money(currency, MIN_BET_GRAM if currency == 'gram' else MIN_BET_GOLD)} до {fmt_money(currency, MAX_BET_GRAM if currency == 'gram' else MAX_BET_GOLD)}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="games")]])
    )
    await call.answer()

@dp.message(GameStates.waiting_bet_amount)
async def diamond_process_bet(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("game") != "diamond":
        return
    
    try:
        bet = float(message.text.replace(",", "."))
        currency = data["currency"]
        
        min_bet = MIN_BET_GRAM if currency == "gram" else MIN_BET_GOLD
        max_bet = MAX_BET_GRAM if currency == "gram" else MAX_BET_GOLD
        
        if bet < min_bet or bet > max_bet:
            await message.answer(f"❌ Ставка должна быть от {fmt_money(currency, min_bet)} до {fmt_money(currency, max_bet)}")
            return
        
        user = get_user(message.from_user.id)
        if user[currency] < bet:
            await message.answer(f"❌ Недостаточно средств. Баланс: {fmt_money(currency, user[currency])}")
            return
        
        bomb_position = create_diamond_field()
        active_diamond_games[message.from_user.id] = {
            "bet": bet,
            "currency": currency,
            "bomb_position": bomb_position,
            "user_id": message.from_user.id,
            "opened": False
        }
        
        await state.clear()
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔹 Клетка 1", callback_data="diamond_cell_0"), InlineKeyboardButton(text="🔹 Клетка 2", callback_data="diamond_cell_1"), InlineKeyboardButton(text="🔹 Клетка 3", callback_data="diamond_cell_2")],
            [InlineKeyboardButton(text="💰 Забрать выигрыш", callback_data="diamond_cashout")],
            [InlineKeyboardButton(text="❌ Закончить игру", callback_data="diamond_cancel")]
        ])
        
        await message.answer(
            f"💎 <b>Игра Алмазы</b>\n\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"🎲 В одной из трёх клеток мина, в двух — выигрыш x2\n\n"
            f"Выбери клетку:",
            reply_markup=kb
        )
        
    except:
        await message.answer("❌ Введи корректную сумму!")

@dp.callback_query(F.data.startswith("diamond_cell_"))
async def diamond_choose_cell(call: CallbackQuery):
    user_id = call.from_user.id
    game = active_diamond_games.get(user_id)
    if not game:
        await call.answer("❌ Игра не найдена!", show_alert=True)
        return
    
    if game.get("opened"):
        await call.answer("❌ Ты уже выбрал клетку!", show_alert=True)
        return
    
    cell = int(call.data.split("_")[2])
    bomb_position = game["bomb_position"]
    bet = game["bet"]
    currency = game["currency"]
    
    game["opened"] = True
    
    if cell == bomb_position:
        update_balance(user_id, currency, -bet)
        add_bet_record(user_id, bet, False, "diamond", currency)
        
        del active_diamond_games[user_id]
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💥" if i == bomb_position else ("✅" if i == cell else "🔹"), callback_data="noop") for i in range(3)],
            [InlineKeyboardButton(text="◀️ В меню", callback_data="games")]
        ])
        
        await call.message.edit_text(
            f"💥 <b>Игра Алмазы</b>\n\n"
            f"❌ Ты выбрал клетку {cell + 1}, а там мина!\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"📊 Результат: <b>ПРОИГРЫШ 😔</b>",
            reply_markup=kb
        )
    else:
        mult = get_diamond_multiplier()
        payout = bet * mult
        
        update_balance(user_id, currency, -bet + payout)
        add_bet_record(user_id, bet, True, "diamond", currency)
        
        del active_diamond_games[user_id]
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅" if i == cell else ("💥" if i == bomb_position else "🔹"), callback_data="noop") for i in range(3)],
            [InlineKeyboardButton(text="◀️ В меню", callback_data="games")]
        ])
        
        await call.message.edit_text(
            f"💎 <b>Игра Алмазы</b>\n\n"
            f"🎉 Ты выбрал клетку {cell + 1} — там сокровище!\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"💸 Выплата: {fmt_money(currency, payout)} (x{mult})\n"
            f"📊 Результат: <b>ПОБЕДА 🎉</b>",
            reply_markup=kb
        )
    
    await call.answer()

@dp.callback_query(F.data == "diamond_cashout")
async def diamond_cashout(call: CallbackQuery):
    await call.answer("❌ Сначала выбери клетку!", show_alert=True)

@dp.callback_query(F.data == "diamond_cancel")
async def diamond_cancel(call: CallbackQuery):
    user_id = call.from_user.id
    game = active_diamond_games.get(user_id)
    if not game:
        await call.answer("❌ Игра не найдена!", show_alert=True)
        return
    
    bet = game["bet"]
    currency = game["currency"]
    
    if not game.get("opened"):
        update_balance(user_id, currency, bet)
        await call.message.edit_text(
            f"❌ <b>Игра Алмазы отменена</b>\n\n"
            f"💰 Ставка возвращена: {fmt_money(currency, bet)}",
            reply_markup=games_menu()
        )
    else:
        await call.message.edit_text(
            f"❌ <b>Игра Алмазы завершена</b>\n\n"
            f"💰 Ставка не возвращается.",
            reply_markup=games_menu()
        )
    
    del active_diamond_games[user_id]
    await call.answer()

# ---------- БАШНЯ ----------
@dp.callback_query(F.data == "game_tower")
async def tower_start(call: CallbackQuery, state: FSMContext):
    if is_banned(call.from_user.id):
        await call.answer("❌ Вы забанены!", show_alert=True)
        return
    
    if not can_play_game(call.from_user.id, "tower"):
        await call.answer("⏰ Подожди 3 секунды перед следующей игрой в Башню!", show_alert=True)
        return
    
    if call.from_user.id in active_tower_games:
        await call.answer("❌ У вас уже есть активная игра в Башню!", show_alert=True)
        return
    
    await state.set_state(GameStates.waiting_currency)
    await state.update_data(game="tower")
    await call.message.edit_text(
        "🗼 <b>Игра Башня</b>\n\n"
        "Выбери валюту для ставки:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Граммы", callback_data="tower_curr_gram")],
            [InlineKeyboardButton(text="🏅 Iris-Gold", callback_data="tower_curr_gold")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="games")]
        ])
    )
    await call.answer()

@dp.callback_query(F.data.startswith("tower_curr_"))
async def tower_set_currency(call: CallbackQuery, state: FSMContext):
    currency = call.data.split("_")[2]
    await state.update_data(currency=currency)
    await state.set_state(GameStates.waiting_tower_mines)
    await call.message.edit_text(
        f"🗼 <b>Игра Башня</b>\n\n"
        f"💰 Введи сумму ставки в {GRAM_NAME if currency == 'gram' else GOLD_NAME}\n"
        f"📊 Лимиты: от {fmt_money(currency, MIN_BET_GRAM if currency == 'gram' else MIN_BET_GOLD)} до {fmt_money(currency, MAX_BET_GRAM if currency == 'gram' else MAX_BET_GOLD)}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="games")]])
    )
    await call.answer()

@dp.message(GameStates.waiting_tower_mines)
async def tower_process_bet(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("game") != "tower":
        return
    
    try:
        bet = float(message.text.replace(",", "."))
        currency = data["currency"]
        
        min_bet = MIN_BET_GRAM if currency == "gram" else MIN_BET_GOLD
        max_bet = MAX_BET_GRAM if currency == "gram" else MAX_BET_GOLD
        
        if bet < min_bet or bet > max_bet:
            await message.answer(f"❌ Ставка должна быть от {fmt_money(currency, min_bet)} до {fmt_money(currency, max_bet)}")
            return
        
        user = get_user(message.from_user.id)
        if user[currency] < bet:
            await message.answer(f"❌ Недостаточно средств. Баланс: {fmt_money(currency, user[currency])}")
            return
        
        await state.update_data(bet=bet)
        await state.set_state(GameStates.waiting_tower_choice)
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💣 1 мина", callback_data="tower_mines_1"), InlineKeyboardButton(text="💣💣 2 мины", callback_data="tower_mines_2")],
            [InlineKeyboardButton(text="💣💣💣 3 мины", callback_data="tower_mines_3"), InlineKeyboardButton(text="💣💣💣💣 4 мины", callback_data="tower_mines_4")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="games")]
        ])
        
        await message.answer(
            f"🗼 <b>Игра Башня</b>\n\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"Выбери количество мин в каждом ряду (1-4):",
            reply_markup=kb
        )
        
    except:
        await message.answer("❌ Введи корректную сумму!")

@dp.callback_query(F.data.startswith("tower_mines_"))
async def tower_set_mines(call: CallbackQuery, state: FSMContext):
    mines = int(call.data.split("_")[2])
    data = await state.get_data()
    bet = data["bet"]
    currency = data["currency"]
    
    bombs = create_tower_bombs(TOWER_ROWS, mines)
    active_tower_games[call.from_user.id] = {
        "bet": bet,
        "currency": currency,
        "mines": mines,
        "level": 0,
        "bombs": bombs,
        "selected": [],
        "user_id": call.from_user.id
    }
    
    await state.clear()
    await show_tower_game(call.message, call.from_user.id)
    await call.answer()

async def show_tower_game(message: Message, user_id: int):
    game = active_tower_games.get(user_id)
    if not game:
        return
    
    level = game["level"]
    bet = game["bet"]
    currency = game["currency"]
    mines = game["mines"]
    bombs = game["bombs"]
    selected = game["selected"]
    
    current_mult = get_tower_multiplier(level, mines)
    current_win = bet * current_mult
    next_mult = get_tower_multiplier(level + 1, mines)
    
    row_buttons = []
    for col in range(TOWER_COLS):
        row_buttons.append(InlineKeyboardButton(text="❔", callback_data=f"tower_cell_{col}"))
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        row_buttons,
        [InlineKeyboardButton(text="💰 Забрать выигрыш", callback_data="tower_cashout")],
        [InlineKeyboardButton(text="❌ Закончить игру", callback_data="tower_cancel")]
    ])
    
    history_text = ""
    if selected:
        history_text = "\n\n📜 <b>История ходов:</b>\n"
        for i, col in enumerate(selected):
            history_text += f"Ряд {i+1}: клетка {col + 1} ✅\n"
    
    text = (
        f"🗼 <b>Игра Башня</b>\n\n"
        f"💰 Ставка: {fmt_money(currency, bet)}\n"
        f"💣 Мин в ряду: {mines}\n"
        f"🏆 Уровень: {level}/{TOWER_ROWS}\n"
        f"📈 Текущий множитель: x{current_mult:.2f}\n"
        f"💸 Потенциальный выигрыш сейчас: {fmt_money(currency, current_win)}\n"
        f"🎯 Следующий множитель: x{next_mult:.2f}\n"
        f"{history_text}\n"
        f"Выбери клетку в {level + 1} ряду:"
    )
    
    await message.answer(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("tower_cell_"))
async def tower_make_choice(call: CallbackQuery):
    user_id = call.from_user.id
    game = active_tower_games.get(user_id)
    if not game:
        await call.answer("❌ Игра не найдена! Начните заново.", show_alert=True)
        return
    
    col = int(call.data.split("_")[2])
    level = game["level"]
    bombs = game["bombs"]
    bet = game["bet"]
    currency = game["currency"]
    mines = game["mines"]
    
    if level >= TOWER_ROWS:
        await call.answer("❌ Игра уже завершена!", show_alert=True)
        return
    
    if bombs[level][col] == 1:
        update_balance(user_id, currency, -bet)
        add_bet_record(user_id, bet, False, "tower", currency)
        
        del active_tower_games[user_id]
        
        kb = InlineKeyboardMarkup(inline_keyboard=[])
        for i in range(TOWER_ROWS):
            row = []
            for j in range(TOWER_COLS):
                if i == level and j == col:
                    row.append(InlineKeyboardButton(text="💥", callback_data="noop"))
                elif bombs[i][j] == 1:
                    row.append(InlineKeyboardButton(text="💣", callback_data="noop"))
                else:
                    row.append(InlineKeyboardButton(text="✅", callback_data="noop"))
            kb.inline_keyboard.append(row)
        kb.inline_keyboard.append([InlineKeyboardButton(text="◀️ В меню", callback_data="games")])
        
        await call.message.edit_text(
            f"💥 <b>Игра Башня</b>\n\n"
            f"❌ Ты попал на мину на {level + 1} уровне, клетка {col + 1}!\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"📊 Результат: <b>ПРОИГРЫШ 😔</b>",
            reply_markup=kb
        )
    else:
        game["selected"].append(col)
        game["level"] += 1
        new_level = game["level"]
        
        if new_level >= TOWER_ROWS:
            mult = get_tower_multiplier(TOWER_ROWS, mines)
            payout = bet * mult
            update_balance(user_id, currency, -bet + payout)
            add_bet_record(user_id, bet, True, "tower", currency)
            
            del active_tower_games[user_id]
            
            await call.message.edit_text(
                f"🏆 <b>Игра Башня</b>\n\n"
                f"🎉 Ты прошёл все {TOWER_ROWS} уровней!\n"
                f"💰 Ставка: {fmt_money(currency, bet)}\n"
                f"💸 Выплата: {fmt_money(currency, payout)} (x{mult:.2f})\n"
                f"📊 Результат: <b>ПОБЕДА 🎉</b>",
                reply_markup=games_menu()
            )
        else:
            await show_tower_game(call.message, user_id)
            await call.answer("✅ Ты выбрал безопасную клетку! Продолжай!")
    
    await call.answer()

@dp.callback_query(F.data == "tower_cashout")
async def tower_cashout(call: CallbackQuery):
    user_id = call.from_user.id
    game = active_tower_games.get(user_id)
    if not game:
        await call.answer("❌ Игра не найдена!", show_alert=True)
        return
    
    level = game["level"]
    if level == 0:
        await call.answer("❌ Сначала сделай хотя бы 1 ход!", show_alert=True)
        return
    
    bet = game["bet"]
    currency = game["currency"]
    mines = game["mines"]
    mult = get_tower_multiplier(level, mines)
    payout = bet * mult
    
    update_balance(user_id, currency, -bet + payout)
    add_bet_record(user_id, bet, True, "tower", currency)
    
    del active_tower_games[user_id]
    
    await call.message.edit_text(
        f"💰 <b>Игра Башня</b>\n\n"
        f"✅ Ты забрал выигрыш на {level} уровне!\n"
        f"💰 Ставка: {fmt_money(currency, bet)}\n"
        f"💸 Выплата: {fmt_money(currency, payout)} (x{mult:.2f})\n"
        f"📊 Результат: <b>ПОБЕДА 🎉</b>",
        reply_markup=games_menu()
    )
    await call.answer()

@dp.callback_query(F.data == "tower_cancel")
async def tower_cancel(call: CallbackQuery):
    user_id = call.from_user.id
    game = active_tower_games.get(user_id)
    if not game:
        await call.answer("❌ Игра не найдена!", show_alert=True)
        return
    
    level = game["level"]
    bet = game["bet"]
    currency = game["currency"]
    
    if level == 0:
        update_balance(user_id, currency, bet)
        await call.message.edit_text(
            f"❌ <b>Игра Башня отменена</b>\n\n"
            f"💰 Ставка возвращена: {fmt_money(currency, bet)}",
            reply_markup=games_menu()
        )
    else:
        await call.message.edit_text(
            f"❌ <b>Игра Башня завершена</b>\n\n"
            f"💰 Ставка не возвращается, так как ты сделал ход(ы).",
            reply_markup=games_menu()
        )
    
    del active_tower_games[user_id]
    await call.answer()

# ---------- ФУТБОЛ ----------
@dp.callback_query(F.data == "game_football")
async def football_start(call: CallbackQuery, state: FSMContext):
    if is_banned(call.from_user.id):
        await call.answer("❌ Вы забанены!", show_alert=True)
        return
    
    if not can_play_game(call.from_user.id, "football"):
        await call.answer("⏰ Подожди 3 секунды перед следующей игрой в Футбол!", show_alert=True)
        return
    
    await state.set_state(GameStates.waiting_currency)
    await state.update_data(game="football")
    await call.message.edit_text(
        "⚽ <b>Игра Футбол</b>\n\n"
        "Выбери валюту для ставки:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Граммы", callback_data="football_curr_gram")],
            [InlineKeyboardButton(text="🏅 Iris-Gold", callback_data="football_curr_gold")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="games")]
        ])
    )
    await call.answer()

@dp.callback_query(F.data.startswith("football_curr_"))
async def football_set_currency(call: CallbackQuery, state: FSMContext):
    currency = call.data.split("_")[2]
    await state.update_data(currency=currency)
    await state.set_state(GameStates.waiting_bet_amount)
    await call.message.edit_text(
        f"⚽ <b>Игра Футбол</b>\n\n"
        f"💰 Введи сумму ставки в {GRAM_NAME if currency == 'gram' else GOLD_NAME}\n"
        f"📊 Лимиты: от {fmt_money(currency, MIN_BET_GRAM if currency == 'gram' else MIN_BET_GOLD)} до {fmt_money(currency, MAX_BET_GRAM if currency == 'gram' else MAX_BET_GOLD)}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="games")]])
    )
    await call.answer()

@dp.message(GameStates.waiting_bet_amount)
async def football_process_bet(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("game") != "football":
        return
    
    try:
        bet = float(message.text.replace(",", "."))
        currency = data["currency"]
        
        min_bet = MIN_BET_GRAM if currency == "gram" else MIN_BET_GOLD
        max_bet = MAX_BET_GRAM if currency == "gram" else MAX_BET_GOLD
        
        if bet < min_bet or bet > max_bet:
            await message.answer(f"❌ Ставка должна быть от {fmt_money(currency, min_bet)} до {fmt_money(currency, max_bet)}")
            return
        
        user = get_user(message.from_user.id)
        if user[currency] < bet:
            await message.answer(f"❌ Недостаточно средств. Баланс: {fmt_money(currency, user[currency])}")
            return
        
        await state.clear()
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚽ ГОЛ (x1.4)", callback_data=f"football_choice_gol_{currency}_{bet}")],
            [InlineKeyboardButton(text="🥅 МИМО (x1.6)", callback_data=f"football_choice_mimo_{currency}_{bet}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="games")]
        ])
        
        await message.answer(
            f"⚽ <b>Игра Футбол</b>\n\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"Выбери исход матча:",
            reply_markup=kb
        )
        
    except:
        await message.answer("❌ Введи корректную сумму!")

@dp.callback_query(F.data.startswith("football_choice_"))
async def football_play_callback(call: CallbackQuery):
    parts = call.data.split("_")
    choice = parts[2]
    currency = parts[3]
    bet = float(parts[4])
    
    win, mult, value = football_play(choice)
    payout = bet * mult if win else 0
    
    update_balance(call.from_user.id, currency, -bet + payout)
    add_bet_record(call.from_user.id, bet, win, "football", currency)
    
    outcome = "ГОЛ 🎉" if value >= 4 else "МИМО 😔"
    result_text = "ПОБЕДА 🎉" if win else "ПРОИГРЫШ 😔"
    
    await call.message.edit_text(
        f"⚽ <b>Игра Футбол</b>\n\n"
        f"🎲 Результат удара: <b>{outcome}</b> (значение {value})\n"
        f"💰 Ставка: {fmt_money(currency, bet)}\n"
        f"💸 Выплата: {fmt_money(currency, payout)}\n"
        f"📊 Результат: <b>{result_text}</b>",
        reply_markup=games_menu()
    )
    await call.answer()

# ---------- БАСКЕТБОЛ ----------
@dp.callback_query(F.data == "game_basket")
async def basket_start(call: CallbackQuery, state: FSMContext):
    if is_banned(call.from_user.id):
        await call.answer("❌ Вы забанены!", show_alert=True)
        return
    
    if not can_play_game(call.from_user.id, "basket"):
        await call.answer("⏰ Подожди 3 секунды перед следующей игрой в Баскетбол!", show_alert=True)
        return
    
    await state.set_state(GameStates.waiting_currency)
    await state.update_data(game="basket")
    await call.message.edit_text(
        "🏀 <b>Игра Баскетбол</b>\n\n"
        "Выбери валюту для ставки:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Граммы", callback_data="basket_curr_gram")],
            [InlineKeyboardButton(text="🏅 Iris-Gold", callback_data="basket_curr_gold")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="games")]
        ])
    )
    await call.answer()

@dp.callback_query(F.data.startswith("basket_curr_"))
async def basket_set_currency(call: CallbackQuery, state: FSMContext):
    currency = call.data.split("_")[2]
    await state.update_data(currency=currency)
    await state.set_state(GameStates.waiting_bet_amount)
    await call.message.edit_text(
        f"🏀 <b>Игра Баскетбол</b>\n\n"
        f"💰 Введи сумму ставки в {GRAM_NAME if currency == 'gram' else GOLD_NAME}\n"
        f"📊 Лимиты: от {fmt_money(currency, MIN_BET_GRAM if currency == 'gram' else MIN_BET_GOLD)} до {fmt_money(currency, MAX_BET_GRAM if currency == 'gram' else MAX_BET_GOLD)}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="games")]])
    )
    await call.answer()

@dp.message(GameStates.waiting_bet_amount)
async def basket_process_bet(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("game") != "basket":
        return
    
    try:
        bet = float(message.text.replace(",", "."))
        currency = data["currency"]
        
        min_bet = MIN_BET_GRAM if currency == "gram" else MIN_BET_GOLD
        max_bet = MAX_BET_GRAM if currency == "gram" else MAX_BET_GOLD
        
        if bet < min_bet or bet > max_bet:
            await message.answer(f"❌ Ставка должна быть от {fmt_money(currency, min_bet)} до {fmt_money(currency, max_bet)}")
            return
        
        user = get_user(message.from_user.id)
        if user[currency] < bet:
            await message.answer(f"❌ Недостаточно средств. Баланс: {fmt_money(currency, user[currency])}")
            return
        
        await state.clear()
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏀 ТОЧНЫЙ БРОСОК (x1.4)", callback_data=f"basket_choice_tochniy_{currency}_{bet}")],
            [InlineKeyboardButton(text="❌ ПРОМАХ (x1.6)", callback_data=f"basket_choice_promah_{currency}_{bet}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="games")]
        ])
        
        await message.answer(
            f"🏀 <b>Игра Баскетбол</b>\n\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"Выбери исход броска:",
            reply_markup=kb
        )
        
    except:
        await message.answer("❌ Введи корректную сумму!")

@dp.callback_query(F.data.startswith("basket_choice_"))
async def basket_play_callback(call: CallbackQuery):
    parts = call.data.split("_")
    choice = parts[2]
    currency = parts[3]
    bet = float(parts[4])
    
    win, mult, value = basket_play(choice)
    payout = bet * mult if win else 0
    
    update_balance(call.from_user.id, currency, -bet + payout)
    add_bet_record(call.from_user.id, bet, win, "basket", currency)
    
    outcome = "ТОЧНЫЙ БРОСОК 🎉" if value in [4,5] else "ПРОМАХ 😔"
    result_text = "ПОБЕДА 🎉" if win else "ПРОИГРЫШ 😔"
    
    await call.message.edit_text(
        f"🏀 <b>Игра Баскетбол</b>\n\n"
        f"🎲 Результат броска: <b>{outcome}</b> (значение {value})\n"
        f"💰 Ставка: {fmt_money(currency, bet)}\n"
        f"💸 Выплата: {fmt_money(currency, payout)}\n"
        f"📊 Результат: <b>{result_text}</b>",
        reply_markup=games_menu()
    )
    await call.answer()

# ---------- КУБИК ----------
@dp.callback_query(F.data == "game_cube")
async def cube_start(call: CallbackQuery, state: FSMContext):
    if is_banned(call.from_user.id):
        await call.answer("❌ Вы забанены!", show_alert=True)
        return
    
    if not can_play_game(call.from_user.id, "cube"):
        await call.answer("⏰ Подожди 3 секунды перед следующей игрой в Кубик!", show_alert=True)
        return
    
    await state.set_state(GameStates.waiting_currency)
    await state.update_data(game="cube")
    await call.message.edit_text(
        "🎲 <b>Игра Кубик</b>\n\n"
        "Выбери валюту для ставки:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Граммы", callback_data="cube_curr_gram")],
            [InlineKeyboardButton(text="🏅 Iris-Gold", callback_data="cube_curr_gold")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="games")]
        ])
    )
    await call.answer()

@dp.callback_query(F.data.startswith("cube_curr_"))
async def cube_set_currency(call: CallbackQuery, state: FSMContext):
    currency = call.data.split("_")[2]
    await state.update_data(currency=currency)
    await state.set_state(GameStates.waiting_bet_amount)
    await call.message.edit_text(
        f"🎲 <b>Игра Кубик</b>\n\n"
        f"💰 Введи сумму ставки в {GRAM_NAME if currency == 'gram' else GOLD_NAME}\n"
        f"📊 Лимиты: от {fmt_money(currency, MIN_BET_GRAM if currency == 'gram' else MIN_BET_GOLD)} до {fmt_money(currency, MAX_BET_GRAM if currency == 'gram' else MAX_BET_GOLD)}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="games")]])
    )
    await call.answer()

@dp.message(GameStates.waiting_bet_amount)
async def cube_process_bet(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("game") != "cube":
        return
    
    try:
        bet = float(message.text.replace(",", "."))
        currency = data["currency"]
        
        min_bet = MIN_BET_GRAM if currency == "gram" else MIN_BET_GOLD
        max_bet = MAX_BET_GRAM if currency == "gram" else MAX_BET_GOLD
        
        if bet < min_bet or bet > max_bet:
            await message.answer(f"❌ Ставка должна быть от {fmt_money(currency, min_bet)} до {fmt_money(currency, max_bet)}")
            return
        
        user = get_user(message.from_user.id)
        if user[currency] < bet:
            await message.answer(f"❌ Недостаточно средств. Баланс: {fmt_money(currency, user[currency])}")
            return
        
        await state.clear()
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="1️⃣", callback_data=f"cube_guess_1_{currency}_{bet}"), InlineKeyboardButton(text="2️⃣", callback_data=f"cube_guess_2_{currency}_{bet}"), InlineKeyboardButton(text="3️⃣", callback_data=f"cube_guess_3_{currency}_{bet}")],
            [InlineKeyboardButton(text="4️⃣", callback_data=f"cube_guess_4_{currency}_{bet}"), InlineKeyboardButton(text="5️⃣", callback_data=f"cube_guess_5_{currency}_{bet}"), InlineKeyboardButton(text="6️⃣", callback_data=f"cube_guess_6_{currency}_{bet}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="games")]
        ])
        
        await message.answer(
            f"🎲 <b>Игра Кубик</b>\n\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"Угадай выпавшее число (1-6):",
            reply_markup=kb
        )
        
    except:
        await message.answer("❌ Введи корректную сумму!")

@dp.callback_query(F.data.startswith("cube_guess_"))
async def cube_play_callback(call: CallbackQuery):
    parts = call.data.split("_")
    guess = int(parts[2])
    currency = parts[3]
    bet = float(parts[4])
    
    win, mult, value = cube_play(guess)
    payout = bet * mult if win else 0
    
    update_balance(call.from_user.id, currency, -bet + payout)
    add_bet_record(call.from_user.id, bet, win, "cube", currency)
    
    result_text = "ПОБЕДА 🎉" if win else "ПРОИГРЫШ 😔"
    
    await call.message.edit_text(
        f"🎲 <b>Игра Кубик</b>\n\n"
        f"🎯 Твой выбор: <b>{guess}</b>\n"
        f"🎲 Выпало: <b>{value}</b>\n"
        f"💰 Ставка: {fmt_money(currency, bet)}\n"
        f"💸 Выплата: {fmt_money(currency, payout)}\n"
        f"📊 Результат: <b>{result_text}</b>",
        reply_markup=games_menu()
    )
    await call.answer()

# ---------- КОСТИ ----------
@dp.callback_query(F.data == "game_dice")
async def dice_start(call: CallbackQuery, state: FSMContext):
    if is_banned(call.from_user.id):
        await call.answer("❌ Вы забанены!", show_alert=True)
        return
    
    if not can_play_game(call.from_user.id, "dice"):
        await call.answer("⏰ Подожди 3 секунды перед следующей игрой в Кости!", show_alert=True)
        return
    
    await state.set_state(GameStates.waiting_currency)
    await state.update_data(game="dice")
    await call.message.edit_text(
        "🎯 <b>Игра Кости</b>\n\n"
        "Выбери валюту для ставки:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Граммы", callback_data="dice_curr_gram")],
            [InlineKeyboardButton(text="🏅 Iris-Gold", callback_data="dice_curr_gold")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="games")]
        ])
    )
    await call.answer()

@dp.callback_query(F.data.startswith("dice_curr_"))
async def dice_set_currency(call: CallbackQuery, state: FSMContext):
    currency = call.data.split("_")[2]
    await state.update_data(currency=currency)
    await state.set_state(GameStates.waiting_bet_amount)
    await call.message.edit_text(
        f"🎯 <b>Игра Кости</b>\n\n"
        f"💰 Введи сумму ставки в {GRAM_NAME if currency == 'gram' else GOLD_NAME}\n"
        f"📊 Лимиты: от {fmt_money(currency, MIN_BET_GRAM if currency == 'gram' else MIN_BET_GOLD)} до {fmt_money(currency, MAX_BET_GRAM if currency == 'gram' else MAX_BET_GOLD)}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="games")]])
    )
    await call.answer()

@dp.message(GameStates.waiting_bet_amount)
async def dice_process_bet(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("game") != "dice":
        return
    
    try:
        bet = float(message.text.replace(",", "."))
        currency = data["currency"]
        
        min_bet = MIN_BET_GRAM if currency == "gram" else MIN_BET_GOLD
        max_bet = MAX_BET_GRAM if currency == "gram" else MAX_BET_GOLD
        
        if bet < min_bet or bet > max_bet:
            await message.answer(f"❌ Ставка должна быть от {fmt_money(currency, min_bet)} до {fmt_money(currency, max_bet)}")
            return
        
        user = get_user(message.from_user.id)
        if user[currency] < bet:
            await message.answer(f"❌ Недостаточно средств. Баланс: {fmt_money(currency, user[currency])}")
            return
        
        await state.clear()
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📈 БОЛЬШЕ 7 (x3.5)", callback_data=f"dice_choice_больше_{currency}_{bet}")],
            [InlineKeyboardButton(text="📉 МЕНЬШЕ 7 (x3.5)", callback_data=f"dice_choice_меньше_{currency}_{bet}")],
            [InlineKeyboardButton(text="🎯 РОВНО 7 (x3.5)", callback_data=f"dice_choice_ровно_{currency}_{bet}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="games")]
        ])
        
        await message.answer(
            f"🎯 <b>Игра Кости</b>\n\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"Выбери исход:",
            reply_markup=kb
        )
        
    except:
        await message.answer("❌ Введи корректную сумму!")

@dp.callback_query(F.data.startswith("dice_choice_"))
async def dice_play_callback(call: CallbackQuery):
    parts = call.data.split("_")
    choice = parts[2]
    currency = parts[3]
    bet = float(parts[4])
    
    win, mult, d1, d2, total = dice_play(choice)
    payout = bet * mult if win else 0
    
    update_balance(call.from_user.id, currency, -bet + payout)
    add_bet_record(call.from_user.id, bet, win, "dice", currency)
    
    result_text = "ПОБЕДА 🎉" if win else "ПРОИГРЫШ 😔"
    
    await call.message.edit_text(
        f"🎯 <b>Игра Кости</b>\n\n"
        f"🎲 Выпало: <b>{d1}</b> + <b>{d2}</b> = <b>{total}</b>\n"
        f"💰 Ставка: {fmt_money(currency, bet)}\n"
        f"💸 Выплата: {fmt_money(currency, payout)}\n"
        f"📊 Результат: <b>{result_text}</b>",
        reply_markup=games_menu()
    )
    await call.answer()

# ========== ПОПОЛНЕНИЕ (STARS) ==========
@dp.callback_query(F.data == "deposit")
async def deposit_start(call: CallbackQuery):
    star_rate = get_star_to_gold_rate()
    await call.message.edit_text(
        f"💎 <b>Пополнение баланса</b>\n\n"
        f"⭐ 1 Star = {fmt_gold(star_rate)}\n\n"
        f"Выбери способ пополнения:",
        reply_markup=deposit_currency_menu()
    )
    await call.answer()

@dp.callback_query(F.data == "deposit_stars")
async def deposit_stars(call: CallbackQuery, state: FSMContext):
    star_rate = get_star_to_gold_rate()
    await call.message.edit_text(
        f"⭐ <b>Пополнение через Stars</b>\n\n"
        f"Курс: 1 Star = {fmt_gold(star_rate)}\n"
        f"Минимальная сумма: 1 Star\n"
        f"Максимальная сумма: 1,000,000 Stars\n\n"
        f"Выбери сумму:",
        reply_markup=stars_amount_menu()
    )
    await call.answer()

@dp.callback_query(F.data.startswith("stars_"))
async def stars_amount_selected(call: CallbackQuery, state: FSMContext):
    if call.data == "stars_custom":
        await state.set_state(DepositStates.waiting_custom_stars)
        await call.message.edit_text(
            "✏️ Введите сумму в Stars (от 1 до 1,000,000):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="deposit_stars")]])
        )
        await call.answer()
        return
    
    stars = int(call.data.split("_")[1])
    star_rate = get_star_to_gold_rate()
    gold = stars * star_rate
    
    await call.message.answer_invoice(
        title="⭐ Пополнение баланса",
        description=f"Получи {fmt_gold(gold)} за {stars} Stars!",
        payload=f"stars_{stars}_{gold}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"{stars} Stars", amount=stars)],
        start_parameter="deposit_stars"
    )
    await call.answer()

@dp.message(DepositStates.waiting_custom_stars)
async def custom_stars_amount(message: Message, state: FSMContext):
    try:
        stars = int(message.text)
        if stars < 1 or stars > 1000000:
            await message.answer("❌ Сумма должна быть от 1 до 1,000,000 Stars")
            return
        star_rate = get_star_to_gold_rate()
        gold = stars * star_rate
        
        await message.answer_invoice(
            title="⭐ Пополнение баланса",
            description=f"Получи {fmt_gold(gold)} за {stars} Stars!",
            payload=f"stars_{stars}_{gold}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label=f"{stars} Stars", amount=stars)],
            start_parameter="deposit_stars"
        )
        await state.clear()
    except:
        await message.answer("❌ Введите целое число Stars")

@dp.pre_checkout_query()
async def pre_checkout_handler(query: PreCheckoutQuery):
    await query.answer(ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    parts = payload.split("_")
    stars = int(parts[1])
    gold = float(parts[2])
    
    new_balance = update_balance(message.from_user.id, "gold", gold)
    update_balance(message.from_user.id, "total_deposited_stars", stars)
    
    star_rate = get_star_to_gold_rate()
    await message.answer(
        f"✅ <b>Пополнение успешно!</b>\n\n"
        f"⭐ Оплачено: {stars} Stars\n"
        f"💰 Получено: {fmt_gold(gold)}\n"
        f"💎 Новый баланс Gold: {fmt_gold(new_balance)}\n\n"
        f"🎮 Приятной игры!",
        reply_markup=main_menu()
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                f"⭐ <b>Новое пополнение через Stars!</b>\n\n"
                f"👤 Пользователь: {mention_user(message.from_user.id, message.from_user.first_name)}\n"
                f"⭐ Stars: {stars}\n"
                f"💰 Получено: {fmt_gold(gold)}"
            )
        except:
            pass

# ========== ПОПОЛНЕНИЕ ГРАММ/ГОЛД (ЗАЯВКИ) ==========
@dp.callback_query(F.data == "deposit_gram")
async def deposit_gram_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(DepositStates.waiting_gram_amount)
    await call.message.edit_text(
        f"💎 <b>Пополнение {GRAM_NAME}</b>\n\n"
        f"1️⃣ Переведите нужную сумму на ID <code>{ADMIN_IDS[0]}</code>\n"
        f"2️⃣ Введите сумму, которую перевели (цифрами):\n\n"
        f"💰 Минимальная сумма: {fmt_gram(1)}\n\n"
        f"После ввода суммы пришлите скриншот перевода!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="deposit")]])
    )
    await call.answer()

@dp.callback_query(F.data == "deposit_gold")
async def deposit_gold_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(DepositStates.waiting_gold_amount)
    await call.message.edit_text(
        f"🏅 <b>Пополнение {GOLD_NAME}</b>\n\n"
        f"1️⃣ Переведите Gold на @{BOT_USERNAME}\n"
        f"2️⃣ Введите сумму, которую перевели (цифрами):\n\n"
        f"💰 Минимальная сумма: {fmt_gold(0.01)}\n\n"
        f"После ввода суммы пришлите скриншот перевода!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="deposit")]])
    )
    await call.answer()

@dp.message(DepositStates.waiting_gram_amount)
async def deposit_gram_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        if amount <= 0:
            await message.answer("❌ Сумма должна быть положительной!")
            return
        
        await state.update_data(amount=amount, currency="gram")
        await state.set_state(DepositStates.waiting_gram_screenshot)
        await message.answer(
            f"📸 <b>Отправьте скриншот перевода</b>\n\n"
            f"💰 Сумма: {fmt_gram(amount)}\n"
            f"📤 Получатель: ID {ADMIN_IDS[0]}\n\n"
            f"После отправки скриншота администратор проверит перевод и пополнит баланс."
        )
    except:
        await message.answer("❌ Введите корректную сумму!")

@dp.message(DepositStates.waiting_gold_amount)
async def deposit_gold_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        if amount <= 0:
            await message.answer("❌ Сумма должна быть положительной!")
            return
        
        await state.update_data(amount=amount, currency="gold")
        await state.set_state(DepositStates.waiting_gold_screenshot)
        await message.answer(
            f"📸 <b>Отправьте скриншот перевода</b>\n\n"
            f"💰 Сумма: {fmt_gold(amount)}\n"
            f"📤 Получатель: @{BOT_USERNAME}\n\n"
            f"После отправки скриншота администратор проверит перевод и пополнит баланс."
        )
    except:
        await message.answer("❌ Введите корректную сумму!")

@dp.message(DepositStates.waiting_gram_screenshot, F.photo)
async def deposit_gram_screenshot(message: Message, state: FSMContext):
    data = await state.get_data()
    amount = data["amount"]
    currency = data["currency"]
    
    req_id = create_deposit_request(message.from_user.id, currency, amount, message.photo[-1].file_id)
    
    await message.answer(
        f"✅ <b>Заявка на пополнение #{req_id} создана!</b>\n\n"
        f"💰 Сумма: {fmt_money(currency, amount)}\n"
        f"📸 Скриншот получен\n\n"
        f"⏳ Администратор проверит заявку в ближайшее время.",
        reply_markup=main_menu()
    )
    
    for admin_id in ADMIN_IDS:
        try:
            caption = (
                f"📥 <b>НОВАЯ ЗАЯВКА НА ПОПОЛНЕНИЕ</b>\n\n"
                f"👤 Пользователь: {mention_user(message.from_user.id, message.from_user.first_name)}\n"
                f"🆔 ID: <code>{message.from_user.id}</code>\n"
                f"💎 Валюта: {GRAM_NAME}\n"
                f"💰 Сумма: {fmt_gram(amount)}\n"
                f"🆔 Заявка: #{req_id}\n\n"
                f"✅ /approve_deposit {req_id} - подтвердить\n"
                f"❌ /decline_deposit {req_id} - отклонить"
            )
            await message.bot.send_photo(admin_id, photo=message.photo[-1].file_id, caption=caption)
        except:
            pass
    
    await state.clear()

@dp.message(DepositStates.waiting_gold_screenshot, F.photo)
async def deposit_gold_screenshot(message: Message, state: FSMContext):
    data = await state.get_data()
    amount = data["amount"]
    currency = data["currency"]
    
    req_id = create_deposit_request(message.from_user.id, currency, amount, message.photo[-1].file_id)
    
    await message.answer(
        f"✅ <b>Заявка на пополнение #{req_id} создана!</b>\n\n"
        f"💰 Сумма: {fmt_money(currency, amount)}\n"
        f"📸 Скриншот получен\n\n"
        f"⏳ Администратор проверит заявку в ближайшее время.",
        reply_markup=main_menu()
    )
    
    for admin_id in ADMIN_IDS:
        try:
            caption = (
                f"📥 <b>НОВАЯ ЗАЯВКА НА ПОПОЛНЕНИЕ</b>\n\n"
                f"👤 Пользователь: {mention_user(message.from_user.id, message.from_user.first_name)}\n"
                f"🆔 ID: <code>{message.from_user.id}</code>\n"
                f"💎 Валюта: {GOLD_NAME}\n"
                f"💰 Сумма: {fmt_gold(amount)}\n"
                f"🆔 Заявка: #{req_id}\n\n"
                f"✅ /approve_deposit {req_id} - подтвердить\n"
                f"❌ /decline_deposit {req_id} - отклонить"
            )
            await message.bot.send_photo(admin_id, photo=message.photo[-1].file_id, caption=caption)
        except:
            pass
    
    await state.clear()

@dp.message(DepositStates.waiting_gram_screenshot)
@dp.message(DepositStates.waiting_gold_screenshot)
async def deposit_screenshot_error(message: Message):
    await message.answer("❌ Пожалуйста, отправьте скриншот перевода (фото)!")

# ========== ВЫВОД ==========
@dp.callback_query(F.data == "withdraw")
async def withdraw_start(call: CallbackQuery):
    await call.message.edit_text("💰 <b>Вывод средств</b>\n\nВыбери валюту для вывода:", reply_markup=withdraw_menu())
    await call.answer()

@dp.callback_query(F.data.startswith("withdraw_"))
async def withdraw_currency(call: CallbackQuery, state: FSMContext):
    currency = call.data.split("_")[1]
    await state.update_data(currency=currency)
    await state.set_state(WithdrawStates.waiting_amount)
    min_amount = MIN_WITHDRAW_GRAM if currency == "gram" else MIN_WITHDRAW_GOLD
    await call.message.edit_text(
        f"💰 Вывод {GRAM_NAME if currency=='gram' else GOLD_NAME}\n"
        f"Минимальная сумма: {fmt_money(currency, min_amount)}\n"
        f"Введите сумму вывода:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="withdraw")]])
    )
    await call.answer()

@dp.message(WithdrawStates.waiting_amount)
async def withdraw_amount_input(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        data = await state.get_data()
        currency = data["currency"]
        min_amount = MIN_WITHDRAW_GRAM if currency == "gram" else MIN_WITHDRAW_GOLD
        if amount < min_amount:
            await message.answer(f"❌ Минимальная сумма {fmt_money(currency, min_amount)}")
            return
        user = get_user(message.from_user.id)
        if user[currency] < amount:
            await message.answer(f"❌ Недостаточно средств. Ваш баланс: {fmt_money(currency, user[currency])}")
            return
        await state.update_data(amount=amount)
        await state.set_state(WithdrawStates.waiting_recipient)
        await message.answer(
            f"📝 <b>Куда отправить средства?</b>\n\n"
            f"💰 Сумма: {fmt_money(currency, amount)}\n\n"
            f"Укажите свой @username или Telegram ID для получения выплаты:"
        )
    except:
        await message.answer("❌ Введите число")

@dp.message(WithdrawStates.waiting_recipient)
async def withdraw_recipient_input(message: Message, state: FSMContext):
    recipient = message.text.strip()
    data = await state.get_data()
    currency = data["currency"]
    amount = data["amount"]
    
    req_id = create_withdraw_request(message.from_user.id, currency, amount, recipient)
    await message.answer(
        f"✅ <b>Заявка на вывод #{req_id} создана!</b>\n\n"
        f"💰 Сумма: {fmt_money(currency, amount)}\n"
        f"📤 Получатель: {recipient}\n\n"
        f"⏳ Администратор рассмотрит заявку в ближайшее время.",
        reply_markup=main_menu()
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                f"📤 <b>Заявка на вывод</b>\n"
                f"👤 {mention_user(message.from_user.id, message.from_user.first_name)}\n"
                f"💎 {GRAM_NAME if currency=='gram' else GOLD_NAME}: {fmt_money(currency, amount)}\n"
                f"📤 Получатель: {recipient}\n"
                f"🆔 Заявка #{req_id}\n\n"
                f"✅ /approve_withdraw {req_id} - подтвердить\n"
                f"❌ /decline_withdraw {req_id} - отклонить"
            )
        except:
            pass
    
    await state.clear()

# ========== ЧЕКИ ==========
@dp.callback_query(F.data == "checks_menu")
async def checks_menu(call: CallbackQuery):
    await call.message.edit_text("🧾 <b>Меню чеков</b>\n\nИспользуй кнопки ниже:", reply_markup=checks_menu_kb())
    await call.answer()

@dp.callback_query(F.data == "check_create")
async def check_create(call: CallbackQuery, state: FSMContext):
    await state.set_state(CheckStates.waiting_currency)
    await call.message.edit_text(
        "Выберите валюту чека:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Граммы", callback_data="check_curr_gram")],
            [InlineKeyboardButton(text="🏅 Iris-Gold", callback_data="check_curr_gold")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="checks_menu")]
        ])
    )
    await call.answer()

@dp.callback_query(F.data.startswith("check_curr_"))
async def check_currency(call: CallbackQuery, state: FSMContext):
    currency = call.data.split("_")[2]
    await state.update_data(currency=currency)
    await state.set_state(CheckStates.waiting_amount)
    min_amount = MIN_BET_GRAM if currency == "gram" else MIN_BET_GOLD
    await call.message.edit_text(
        f"💰 Введите сумму на один чек (мин. {fmt_money(currency, min_amount)}):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="checks_menu")]])
    )
    await call.answer()

@dp.message(CheckStates.waiting_amount)
async def check_amount_input(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        data = await state.get_data()
        currency = data["currency"]
        min_amount = MIN_BET_GRAM if currency == "gram" else MIN_BET_GOLD
        if amount < min_amount:
            await message.answer(f"❌ Минимальная сумма {fmt_money(currency, min_amount)}")
            return
        await state.update_data(amount=amount)
        await state.set_state(CheckStates.waiting_count)
        await message.answer("📦 Введите количество активаций (1-100):")
    except:
        await message.answer("❌ Введите число")

@dp.message(CheckStates.waiting_count)
async def check_count_input(message: Message, state: FSMContext):
    try:
        count = int(message.text)
        if count < 1 or count > 100:
            await message.answer("❌ Количество от 1 до 100")
            return
        data = await state.get_data()
        amount = data["amount"]
        currency = data["currency"]
        ok, result = create_check(message.from_user.id, amount, currency, count)
        await state.clear()
        if ok:
            await message.answer(
                f"✅ Чек создан!\n🎫 Код: <code>{result}</code>\n"
                f"💰 Сумма: {fmt_money(currency, amount)}\n"
                f"📦 Активаций: {count}",
                reply_markup=main_menu()
            )
        else:
            await message.answer(f"❌ {result}", reply_markup=main_menu())
    except:
        await message.answer("❌ Введите целое число")

@dp.callback_query(F.data == "check_claim")
async def check_claim(call: CallbackQuery, state: FSMContext):
    await state.set_state(CheckStates.waiting_code)
    await call.message.edit_text("🎫 Введите код чека:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="checks_menu")]]))
    await call.answer()

@dp.message(CheckStates.waiting_code)
async def claim_code_input(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    ok, result, reward, currency = claim_check(message.from_user.id, code)
    await state.clear()
    if ok:
        await message.answer(f"✅ {result}\n💰 Новый баланс: {fmt_money(currency, get_user(message.from_user.id)[currency])}", reply_markup=main_menu())
    else:
        await message.answer(f"❌ {result}", reply_markup=main_menu())

@dp.callback_query(F.data == "check_my")
async def my_checks(call: CallbackQuery):
    checks = get_user_checks(call.from_user.id)
    if not checks:
        await call.message.edit_text("📭 У вас нет созданных чеков", reply_markup=back_button())
    else:
        text = "🧾 Ваши чеки:\n"
        for c in checks:
            curr_name = GRAM_NAME if c['currency'] == 'gram' else GOLD_NAME
            text += f"🎫 <code>{c['code']}</code> | {fmt_money(c['currency'], c['per_user'])} | {curr_name} | осталось: {c['remaining']}\n"
        await call.message.edit_text(text, reply_markup=back_button())
    await call.answer()

# ========== ПРОМОКОДЫ ==========
@dp.callback_query(F.data == "promo_menu")
async def promo_menu(call: CallbackQuery, state: FSMContext):
    await state.set_state(PromoStates.waiting_code)
    await call.message.edit_text("🎟 Введите промокод:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]]))
    await call.answer()

@dp.message(PromoStates.waiting_code)
async def activate_promo_code(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    ok, result, rg, rgo = redeem_promo(message.from_user.id, code)
    await state.clear()
    if ok:
        text = f"🎉 {result}\n"
        if rg: text += f"💎 +{fmt_gram(rg)}\n"
        if rgo: text += f"🏅 +{fmt_gold(rgo)}\n"
        user = get_user(message.from_user.id)
        text += f"\n💰 Новый баланс:\n💎 {fmt_gram(user['gram'])}\n🏅 {fmt_gold(user['gold'])}"
        await message.answer(text, reply_markup=main_menu())
    else:
        await message.answer(f"❌ {result}", reply_markup=main_menu())

# ========== АДМИН-ПАНЕЛЬ ==========
@dp.callback_query(F.data == "admin_panel")
async def admin_panel(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    await call.message.edit_text("⚙️ <b>Админ-панель</b>\n\nВыберите действие:", reply_markup=admin_panel_menu())
    await call.answer()

@dp.callback_query(F.data == "admin_all_users")
async def admin_all_users(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    users = get_all_users()
    if not users:
        await call.message.edit_text("📭 Нет пользователей")
        return
    text = "👥 <b>Все пользователи</b>\n\n"
    for u in users[:20]:
        status = "👑" if u["is_admin"] else "👤"
        if u["is_banned"]:
            status += "🔒"
        name = u["username"] or u["first_name"] or f"ID{u['user_id']}"
        text += f"{status} {mention_user(int(u['user_id']), name)} | 💎 {fmt_gram(u['gram'])} | 🏅 {fmt_gold(u['gold'])}\n"
    if len(users) > 20:
        text += f"\n... и ещё {len(users) - 20} пользователей"
    await call.message.edit_text(text, reply_markup=back_button())
    await call.answer()

@dp.callback_query(F.data == "admin_give")
async def admin_give_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_user_id)
    await call.message.edit_text("💰 Введите ID пользователя для выдачи валюты:", reply_markup=back_button())
    await call.answer()

@dp.callback_query(F.data == "admin_take")
async def admin_take_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_user_id)
    await state.update_data(action="take")
    await call.message.edit_text("🔫 Введите ID пользователя для списания валюты:", reply_markup=back_button())
    await call.answer()

@dp.callback_query(F.data == "admin_set_admin")
async def admin_set_admin_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_user_id)
    await state.update_data(action="set_admin")
    await call.message.edit_text("👑 Введите ID пользователя для выдачи прав администратора:", reply_markup=back_button())
    await call.answer()

@dp.callback_query(F.data == "admin_remove_admin")
async def admin_remove_admin_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_user_id)
    await state.update_data(action="remove_admin")
    await call.message.edit_text("👑 Введите ID пользователя для снятия прав администратора:", reply_markup=back_button())
    await call.answer()

@dp.callback_query(F.data == "admin_ban")
async def admin_ban_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_user_id)
    await state.update_data(action="ban")
    await call.message.edit_text("🔒 Введите ID пользователя для блокировки:", reply_markup=back_button())
    await call.answer()

@dp.callback_query(F.data == "admin_unban")
async def admin_unban_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_user_id)
    await state.update_data(action="unban")
    await call.message.edit_text("🔓 Введите ID пользователя для разблокировки:", reply_markup=back_button())
    await call.answer()

@dp.callback_query(F.data == "admin_reset_balances")
async def admin_reset_balances(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    reset_all_balances()
    add_admin_log(call.from_user.id, "reset_all_balances")
    await call.message.edit_text("✅ Все балансы пользователей сброшены до стандартных (500 грамм, 0 голд)!", reply_markup=admin_panel_menu())
    await call.answer()

@dp.callback_query(F.data == "admin_set_rate")
async def admin_set_rate_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_new_rate)
    current_rate = get_star_to_gold_rate()
    await call.message.edit_text(
        f"💱 <b>Изменение курса Stars</b>\n\n"
        f"Текущий курс: 1 Star = {fmt_gold(current_rate)}\n\n"
        f"Введите новый курс (например: 0.70 или 1.5):\n"
        f"Пример: <code>0.85</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]])
    )
    await call.answer()

@dp.message(AdminStates.waiting_new_rate)
async def admin_set_rate(message: Message, state: FSMContext):
    try:
        new_rate = float(message.text.replace(",", "."))
        if new_rate <= 0:
            await message.answer("❌ Курс должен быть положительным числом!")
            return
        set_star_to_gold_rate(new_rate)
        add_admin_log(message.from_user.id, f"set_star_rate_{new_rate}")
        await message.answer(
            f"✅ Курс успешно изменён!\n\n"
            f"⭐ 1 Star = {fmt_gold(new_rate)}",
            reply_markup=admin_panel_menu()
        )
        await state.clear()
    except:
        await message.answer("❌ Введите корректное число!")

@dp.message(AdminStates.waiting_user_id)
async def admin_get_user_id(message: Message, state: FSMContext):
    try:
        target_id = int(message.text)
        data = await state.get_data()
        action = data.get("action", "give")
        
        if action in ["give", "take"]:
            await state.update_data(target_id=target_id)
            await state.set_state(AdminStates.waiting_currency)
            await message.answer("💎 Введите валюту (gram или gold):")
        elif action == "set_admin":
            conn = get_db()
            conn.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (str(target_id),))
            conn.commit()
            conn.close()
            add_admin_log(message.from_user.id, "set_admin", target_id)
            await message.answer(f"✅ Пользователь {target_id} назначен администратором!", reply_markup=admin_panel_menu())
            await state.clear()
        elif action == "remove_admin":
            if target_id == ADMIN_IDS[0]:
                await message.answer("❌ Нельзя снять админа с главного администратора!")
            else:
                conn = get_db()
                conn.execute("UPDATE users SET is_admin = 0 WHERE user_id = ?", (str(target_id),))
                conn.commit()
                conn.close()
                add_admin_log(message.from_user.id, "remove_admin", target_id)
                await message.answer(f"✅ Пользователь {target_id} лишён прав администратора!", reply_markup=admin_panel_menu())
            await state.clear()
        elif action == "ban":
            if target_id in ADMIN_IDS:
                await message.answer("❌ Нельзя заблокировать администратора!")
            else:
                conn = get_db()
                conn.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (str(target_id),))
                conn.commit()
                conn.close()
                add_admin_log(message.from_user.id, "ban", target_id)
                await message.answer(f"✅ Пользователь {target_id} заблокирован!", reply_markup=admin_panel_menu())
            await state.clear()
        elif action == "unban":
            conn = get_db()
            conn.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (str(target_id),))
            conn.commit()
            conn.close()
            add_admin_log(message.from_user.id, "unban", target_id)
            await message.answer(f"✅ Пользователь {target_id} разблокирован!", reply_markup=admin_panel_menu())
            await state.clear()
    except:
        await message.answer("❌ Введите корректный ID пользователя!")

@dp.message(AdminStates.waiting_currency)
async def admin_get_currency(message: Message, state: FSMContext):
    currency = message.text.lower()
    if currency not in ["gram", "gold"]:
        await message.answer("❌ Валюта должна быть 'gram' или 'gold'")
        return
    await state.update_data(currency=currency)
    await state.set_state(AdminStates.waiting_amount)
    await message.answer("💰 Введите сумму:")

@dp.message(AdminStates.waiting_amount)
async def admin_get_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        if amount <= 0:
            await message.answer("❌ Сумма должна быть положительной")
            return
        data = await state.get_data()
        target_id = data["target_id"]
        currency = data["currency"]
        action = data.get("action", "give")
        
        if action == "give":
            new_balance = update_balance(target_id, currency, amount)
            add_admin_log(message.from_user.id, f"give_{currency}", target_id, amount)
            await message.answer(f"✅ Выдано {fmt_money(currency, amount)} пользователю {target_id}\n💰 Новый баланс: {fmt_money(currency, new_balance)}", reply_markup=admin_panel_menu())
            try:
                await message.bot.send_message(target_id, f"✅ Вам начислено {fmt_money(currency, amount)}!\n💰 Новый баланс: {fmt_money(currency, new_balance)}")
            except:
                pass
        elif action == "take":
            user = get_user(target_id)
            if user[currency] < amount:
                await message.answer(f"❌ У пользователя недостаточно средств! Баланс: {fmt_money(currency, user[currency])}")
                return
            new_balance = update_balance(target_id, currency, -amount)
            add_admin_log(message.from_user.id, f"take_{currency}", target_id, amount)
            await message.answer(f"✅ Забрано {fmt_money(currency, amount)} у пользователя {target_id}\n💰 Новый баланс: {fmt_money(currency, new_balance)}", reply_markup=admin_panel_menu())
            try:
                await message.bot.send_message(target_id, f"⚠️ С вашего баланса списано {fmt_money(currency, amount)}!\n💰 Новый баланс: {fmt_money(currency, new_balance)}")
            except:
                pass
        
        await state.clear()
    except:
        await message.answer("❌ Введите корректную сумму!")

@dp.callback_query(F.data == "admin_withdraw_requests")
async def admin_withdraw_requests(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    requests = get_pending_withdraws()
    if not requests:
        await call.message.edit_text("📭 Нет активных заявок на вывод", reply_markup=back_button())
        await call.answer()
        return
    text = "📥 <b>Заявки на вывод</b>\n\n"
    for r in requests:
        text += f"🆔 #{r['id']} | {mention_user(int(r['user_id']))} | {fmt_money(r['currency'], r['amount'])} | {r['recipient']}\n"
    await call.message.edit_text(text, reply_markup=back_button())
    await call.answer()

@dp.callback_query(F.data == "admin_deposit_requests")
async def admin_deposit_requests(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    requests = get_pending_deposits()
    if not requests:
        await call.message.edit_text("📭 Нет активных заявок на пополнение", reply_markup=back_button())
        await call.answer()
        return
    text = "📤 <b>Заявки на пополнение</b>\n\n"
    for r in requests:
        text += f"🆔 #{r['id']} | {mention_user(int(r['user_id']))} | {fmt_money(r['currency'], r['amount'])} | есть скриншот\n"
    await call.message.edit_text(text, reply_markup=back_button())
    await call.answer()

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    stats = get_bot_stats()
    star_rate = get_star_to_gold_rate()
    await call.message.edit_text(
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: {stats['total_users']}\n"
        f"🎲 Всего ставок: {stats['total_bets']}\n"
        f"🏆 Всего побед: {stats['total_wins']}\n"
        f"💎 Пополнено грамм: {fmt_gram(stats['total_deposited_gram'])}\n"
        f"🏅 Пополнено Gold: {fmt_gold(stats['total_deposited_gold'])}\n"
        f"⭐ Пополнено Stars: {stats['total_deposited_stars']}\n"
        f"⭐ Текущий курс: 1 Star = {fmt_gold(star_rate)}\n"
        f"📤 Выведено грамм: {fmt_gram(stats['total_withdrawn_gram'])}\n"
        f"📤 Выведено Gold: {fmt_gold(stats['total_withdrawn_gold'])}",
        reply_markup=back_button()
    )
    await call.answer()

@dp.callback_query(F.data == "admin_logs")
async def admin_logs(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    logs = get_admin_logs(20)
    if not logs:
        await call.message.edit_text("📭 Логов пока нет", reply_markup=back_button())
        await call.answer()
        return
    text = "📜 <b>Последние действия админов</b>\n\n"
    for log in logs:
        date = datetime.fromtimestamp(log["timestamp"]).strftime("%d.%m %H:%M")
        text += f"🕐 {date} | 👤 {log['admin_id']} | {log['action']}"
        if log['target_id']:
            text += f" | 🎯 {log['target_id']}"
        if log['amount']:
            text += f" | 💰 {log['amount']}"
        text += "\n"
    await call.message.edit_text(text, reply_markup=back_button())
    await call.answer()

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_broadcast)
    await call.message.edit_text("📢 Введите сообщение для рассылки:", reply_markup=back_button())
    await call.answer()

@dp.message(AdminStates.waiting_broadcast)
async def admin_broadcast_send(message: Message, state: FSMContext):
    users = get_all_users()
    success = 0
    fail = 0
    
    await message.answer("🚀 Начинаю рассылку...")
    
    for user in users:
        try:
            await message.bot.send_message(int(user["user_id"]), message.text)
            success += 1
            await asyncio.sleep(0.05)
        except:
            fail += 1
    
    await message.answer(f"✅ Рассылка завершена!\n📨 Доставлено: {success}\n❌ Ошибок: {fail}", reply_markup=admin_panel_menu())
    await state.clear()

@dp.callback_query(F.data == "admin_create_promo")
async def admin_create_promo_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_promo_code)
    await call.message.edit_text("🎟 Введите код промокода:", reply_markup=back_button())
    await call.answer()

@dp.message(AdminStates.waiting_promo_code)
async def admin_create_promo_code(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    await state.update_data(promo_code=code)
    await state.set_state(AdminStates.waiting_promo_reward_gram)
    await message.answer("💎 Введите награду в Граммах (число):")

@dp.message(AdminStates.waiting_promo_reward_gram)
async def admin_create_promo_reward_gram(message: Message, state: FSMContext):
    try:
        reward_gram = float(message.text.replace(",", "."))
        await state.update_data(promo_reward_gram=reward_gram)
        await state.set_state(AdminStates.waiting_promo_reward_gold)
        await message.answer("🏅 Введите награду в Iris-Gold (число):")
    except:
        await message.answer("❌ Введите число!")

@dp.message(AdminStates.waiting_promo_reward_gold)
async def admin_create_promo_reward_gold(message: Message, state: FSMContext):
    try:
        reward_gold = float(message.text.replace(",", "."))
        await state.update_data(promo_reward_gold=reward_gold)
        await state.set_state(AdminStates.waiting_promo_activations)
        await message.answer("🔢 Введите количество активаций (целое число):")
    except:
        await message.answer("❌ Введите число!")

@dp.message(AdminStates.waiting_promo_activations)
async def admin_create_promo_activations(message: Message, state: FSMContext):
    try:
        activations = int(message.text)
        if activations <= 0:
            await message.answer("❌ Количество активаций должно быть больше 0")
            return
        data = await state.get_data()
        code = data["promo_code"]
        reward_gram = data["promo_reward_gram"]
        reward_gold = data["promo_reward_gold"]
        
        create_promo(code, reward_gram, reward_gold, activations)
        add_admin_log(message.from_user.id, "create_promo", None, None)
        
        await message.answer(
            f"✅ Промокод создан!\n"
            f"🎫 Код: <code>{code}</code>\n"
            f"💎 Награда: {fmt_gram(reward_gram)}\n"
            f"🏅 Награда: {fmt_gold(reward_gold)}\n"
            f"🔢 Активаций: {activations}",
            reply_markup=admin_panel_menu()
        )
        await state.clear()
    except:
        await message.answer("❌ Введите целое число!")

# ========== АДМИН-КОМАНДЫ ДЛЯ ЗАЯВОК ==========
@dp.message(Command("approve_deposit"))
async def approve_deposit_cmd(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только для админов!")
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("📝 /approve_deposit ID")
        return
    try:
        req_id = int(parts[1])
        if approve_deposit(req_id):
            conn = get_db()
            row = conn.execute("SELECT user_id, currency, amount FROM deposit_requests WHERE id = ?", (req_id,)).fetchone()
            conn.close()
            if row:
                await message.bot.send_message(int(row["user_id"]), f"✅ Ваша заявка на пополнение #{req_id} одобрена!\n💰 Начислено: {fmt_money(row['currency'], row['amount'])}")
                user = get_user(int(row["user_id"]))
                if user and user["referrer_id"]:
                    referrer_id = int(user["referrer_id"])
                    ref_bonus = row["amount"] * 0.05
                    update_balance(referrer_id, "gram", ref_bonus)
                    conn2 = get_db()
                    conn2.execute("UPDATE users SET referral_earned = referral_earned + ? WHERE user_id = ?", (ref_bonus, str(referrer_id)))
                    conn2.commit()
                    conn2.close()
            add_admin_log(message.from_user.id, "approve_deposit", None, None)
            await message.answer(f"✅ Заявка #{req_id} подтверждена")
        else:
            await message.answer(f"❌ Заявка #{req_id} не найдена")
    except:
        await message.answer("❌ Ошибка!")

@dp.message(Command("decline_deposit"))
async def decline_deposit_cmd(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только для админов!")
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("📝 /decline_deposit ID")
        return
    try:
        req_id = int(parts[1])
        if decline_deposit(req_id):
            conn = get_db()
            row = conn.execute("SELECT user_id FROM deposit_requests WHERE id = ?", (req_id,)).fetchone()
            conn.close()
            if row:
                await message.bot.send_message(int(row["user_id"]), f"❌ Ваша заявка на пополнение #{req_id} отклонена.")
            add_admin_log(message.from_user.id, "decline_deposit", None, None)
            await message.answer(f"✅ Заявка #{req_id} отклонена")
        else:
            await message.answer(f"❌ Заявка #{req_id} не найдена")
    except:
        await message.answer("❌ Ошибка!")

@dp.message(Command("approve_withdraw"))
async def approve_withdraw_cmd(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только для админов!")
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("📝 /approve_withdraw ID")
        return
    try:
        req_id = int(parts[1])
        if approve_withdraw(req_id):
            conn = get_db()
            row = conn.execute("SELECT user_id, currency, amount, recipient FROM withdraw_requests WHERE id = ?", (req_id,)).fetchone()
            conn.close()
            if row:
                await message.bot.send_message(int(row["user_id"]), f"✅ Ваша заявка на вывод #{req_id} одобрена!\n💰 Сумма: {fmt_money(row['currency'], row['amount'])}\n📤 Отправлено на: {row['recipient']}")
            add_admin_log(message.from_user.id, "approve_withdraw", None, None)
            await message.answer(f"✅ Заявка #{req_id} подтверждена")
        else:
            await message.answer(f"❌ Заявка #{req_id} не найдена")
    except:
        await message.answer("❌ Ошибка!")

@dp.message(Command("decline_withdraw"))
async def decline_withdraw_cmd(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только для админов!")
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("📝 /decline_withdraw ID")
        return
    try:
        req_id = int(parts[1])
        if decline_withdraw(req_id):
            conn = get_db()
            row = conn.execute("SELECT user_id FROM withdraw_requests WHERE id = ?", (req_id,)).fetchone()
            conn.close()
            if row:
                await message.bot.send_message(int(row["user_id"]), f"❌ Ваша заявка на вывод #{req_id} отклонена.")
            add_admin_log(message.from_user.id, "decline_withdraw", None, None)
            await message.answer(f"✅ Заявка #{req_id} отклонена")
        else:
            await message.answer(f"❌ Заявка #{req_id} не найдена")
    except:
        await message.answer("❌ Ошибка!")

# ========== ТЕКСТОВЫЕ КОМАНДЫ ==========
@dp.message(F.text.lower().in_(["б", "баланс"]))
async def balance_text_cmd(message: Message):
    if is_banned(message.from_user.id):
        await message.answer("❌ Вы забанены!")
        return
    user = get_user(message.from_user.id)
    await message.answer(
        f"💰 <b>Твой баланс</b>\n\n"
        f"{mention_user(message.from_user.id, message.from_user.first_name)}, твой баланс:\n\n"
        f"💎 {GRAM_NAME}: {fmt_gram(user['gram'])}\n"
        f"🏅 {GOLD_NAME}: {fmt_gold(user['gold'])}"
    )

@dp.message(F.text.lower() == "профиль")
async def profile_text_cmd(message: Message):
    if is_banned(message.from_user.id):
        await message.answer("❌ Вы забанены!")
        return
    user = get_user(message.from_user.id)
    wins = user["total_wins"] or 0
    bets = user["total_bets"] or 1
    wr = (wins / bets) * 100
    admin_status = "👑 Администратор" if user["is_admin"] else "👤 Пользователь"
    star_rate = get_star_to_gold_rate()
    await message.answer(
        f"👤 <b>Профиль</b>\n\n"
        f"{mention_user(message.from_user.id, message.from_user.first_name)}, твоя статистика:\n\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n"
        f"📊 Статус: {admin_status}\n\n"
        f"💰 Баланс:\n💎 {fmt_gram(user['gram'])}\n🏅 {fmt_gold(user['gold'])}\n\n"
        f"📊 Статистика:\n"
        f"💎 Пополнено: {fmt_gram(user['total_deposited_gram'] or 0)}\n"
        f"🏅 Пополнено: {fmt_gold(user['total_deposited_gold'] or 0)}\n"
        f"⭐ Пополнено Stars: {user['total_deposited_stars'] or 0}\n"
        f"📤 Выведено: {fmt_gram(user['total_withdrawn_gram'] or 0)} / {fmt_gold(user['total_withdrawn_gold'] or 0)}\n"
        f"🎲 Ставок: {bets} | Побед: {wins} ({wr:.1f}%)\n\n"
        f"⭐ Курс Stars: 1 Star = {fmt_gold(star_rate)}\n\n"
        f"📊 Лимиты:\n💎 {fmt_gram(MIN_BET_GRAM)}-{fmt_gram(MAX_BET_GRAM)} | 🏅 {fmt_gold(MIN_BET_GOLD)}-{fmt_gold(MAX_BET_GOLD)}\n"
        f"💎 Мин. вывод: {fmt_gram(MIN_WITHDRAW_GRAM)}\n🏅 Мин. вывод: {fmt_gold(MIN_WITHDRAW_GOLD)}"
    )

@dp.message(F.text.lower() == "топ")
async def top_text_cmd(message: Message):
    if is_banned(message.from_user.id):
        await message.answer("❌ Вы забанены!")
        return
    top_gram = get_top_players("gram", 5)
    top_gold = get_top_players("gold", 5)
    medals = ["🥇", "🥈", "🥉"]
    text = "🏆 <b>Топ игроков</b>\n\n💎 <b>Граммы:</b>\n"
    for i, p in enumerate(top_gram):
        medal = medals[i] if i < 3 else f"{i+1}."
        name = p["username"] or f"ID{p['user_id']}"
        text += f"{medal} @{name} — {fmt_gram(p['gram'])}\n"
    text += "\n🏅 <b>Iris-Gold:</b>\n"
    for i, p in enumerate(top_gold):
        medal = medals[i] if i < 3 else f"{i+1}."
        name = p["username"] or f"ID{p['user_id']}"
        text += f"{medal} @{name} — {fmt_gold(p['gold'])}\n"
    await message.answer(text)

@dp.message(F.text.lower() == "бонус")
async def bonus_text_cmd(message: Message):
    if is_banned(message.from_user.id):
        await message.answer("❌ Вы забанены!")
        return
    user_id = message.from_user.id
    user = get_user(user_id)
    last = user["last_bonus"] or 0
    now = now_ts()
    if now - last < 43200:
        left = 43200 - (now - last)
        h = left // 3600
        m = (left % 3600) // 60
        await message.answer(f"⏰ Бонус через {h}ч {m}мин")
        return
    reward = random.randint(BONUS_GRAM_MIN, BONUS_GRAM_MAX)
    update_balance(user_id, "gram", reward)
    conn = get_db()
    conn.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?", (now, str(user_id)))
    conn.commit()
    conn.close()
    await message.answer(f"🎁 Ежедневный бонус!\n💎 +{fmt_gram(reward)}")

@dp.message(F.text.lower() == "реф")
async def ref_text_cmd(message: Message):
    if is_banned(message.from_user.id):
        await message.answer("❌ Вы забанены!")
        return
    
    user = get_user(message.from_user.id)
    ref_link = f"https://t.me/{BOT_USERNAME}?start={message.from_user.id}"
    
    text = (
        f"🫶 <b>{mention_user(message.from_user.id, message.from_user.first_name)}</b>, зарабатывай, приглашая друзей:\n\n"
        f"💰 Баланс: {fmt_gram(user['gram'])}\n"
        f"💸 Всего заработано: {fmt_gram(user['referral_earned'] or 0)}\n"
        f"🧲 Приглашено друзей: {user['referral_count'] or 0}\n\n"
        f"🔗 <b>Твоя реферальная ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"🎁 <b>Что ты получаешь:</b>\n"
        f"• 🤑 1500 {GRAM_NAME} — за регистрацию друга\n"
        f"• 💎 5% — с каждого доната друга\n"
        f"• 💰 1% — с каждого проигрыша друга"
    )
    
    await message.answer(text)

@dp.message(F.text.lower() == "чеки")
async def checks_text_cmd(message: Message):
    if is_banned(message.from_user.id):
        await message.answer("❌ Вы забанены!")
        return
    await message.answer("🧾 <b>Меню чеков</b>\n\nИспользуй кнопки ниже:", reply_markup=checks_menu_kb())

@dp.message(F.text.lower().startswith("промокод"))
async def promo_text_cmd(message: Message, state: FSMContext):
    if is_banned(message.from_user.id):
        await message.answer("❌ Вы забанены!")
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("❌ Формат: `промокод КОД`", parse_mode="Markdown")
        return
    code = parts[1].upper()
    ok, result, rg, rgo = redeem_promo(message.from_user.id, code)
    if ok:
        text = f"🎉 {result}\n"
        if rg: text += f"💎 +{fmt_gram(rg)}\n"
        if rgo: text += f"🏅 +{fmt_gold(rgo)}\n"
        user = get_user(message.from_user.id)
        text += f"\n💰 Новый баланс:\n💎 {fmt_gram(user['gram'])}\n🏅 {fmt_gold(user['gold'])}"
        await message.answer(text)
    else:
        await message.answer(f"❌ {result}")

# ========== ТЕКСТОВЫЕ КОМАНДЫ ДЛЯ ИГР ==========
@dp.message(F.text.lower().startswith("золото"))
async def gold_text_cmd(message: Message):
    if is_banned(message.from_user.id):
        await message.answer("❌ Вы забанены!")
        return
    
    if not can_play_game(message.from_user.id, "gold"):
        await message.answer("⏰ Подожди 3 секунды перед следующей игрой в Золото!")
        return
    
    parts = message.text.lower().split()
    if len(parts) != 4:
        await message.answer("❌ Формат: `золото 100 gram gold`\nВарианты: gold, silver, bronze", parse_mode="Markdown")
        return
    
    try:
        bet = float(parts[1])
        currency = parts[2]
        choice = parts[3]
        
        if currency not in ["gram", "gold"]:
            await message.answer("❌ Валюта должна быть 'gram' или 'gold'")
            return
        
        if choice not in ["gold", "silver", "bronze"]:
            await message.answer("❌ Выбери: gold, silver, bronze")
            return
        
        min_bet = MIN_BET_GRAM if currency == "gram" else MIN_BET_GOLD
        max_bet = MAX_BET_GRAM if currency == "gram" else MAX_BET_GOLD
        
        if bet < min_bet or bet > max_bet:
            await message.answer(f"❌ Ставка должна быть от {fmt_money(currency, min_bet)} до {fmt_money(currency, max_bet)}")
            return
        
        user = get_user(message.from_user.id)
        if user[currency] < bet:
            await message.answer(f"❌ Недостаточно средств. Баланс: {fmt_money(currency, user[currency])}")
            return
        
        update_balance(message.from_user.id, currency, -bet)
        
        win = random.choice([True, False])
        mult = 2.0 if win else 0
        payout = bet * mult if win else 0
        if win:
            update_balance(message.from_user.id, currency, payout)
        add_bet_record(message.from_user.id, bet, win, "gold", currency)
        
        result_text = "ПОБЕДА 🎉" if win else "ПРОИГРЫШ 😔"
        
        await message.answer(
            f"🥇 <b>Игра Золото</b>\n\n"
            f"🎲 Твой выбор: {choice}\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"💸 Выплата: {fmt_money(currency, payout)}\n"
            f"📊 Результат: <b>{result_text}</b>"
        )
    except:
        await message.answer("❌ Ошибка! Пример: `золото 100 gram gold`", parse_mode="Markdown")

@dp.message(F.text.lower().startswith("алмазы"))
async def diamond_text_cmd(message: Message):
    if is_banned(message.from_user.id):
        await message.answer("❌ Вы забанены!")
        return
    
    if not can_play_game(message.from_user.id, "diamond"):
        await message.answer("⏰ Подожди 3 секунды перед следующей игрой в Алмазы!")
        return
    
    parts = message.text.lower().split()
    if len(parts) != 4:
        await message.answer("❌ Формат: `алмазы 100 gram diamond`\nВарианты: diamond, ruby, emerald", parse_mode="Markdown")
        return
    
    try:
        bet = float(parts[1])
        currency = parts[2]
        choice = parts[3]
        
        if currency not in ["gram", "gold"]:
            await message.answer("❌ Валюта должна быть 'gram' или 'gold'")
            return
        
        if choice not in ["diamond", "ruby", "emerald"]:
            await message.answer("❌ Выбери: diamond, ruby, emerald")
            return
        
        min_bet = MIN_BET_GRAM if currency == "gram" else MIN_BET_GOLD
        max_bet = MAX_BET_GRAM if currency == "gram" else MAX_BET_GOLD
        
        if bet < min_bet or bet > max_bet:
            await message.answer(f"❌ Ставка должна быть от {fmt_money(currency, min_bet)} до {fmt_money(currency, max_bet)}")
            return
        
        user = get_user(message.from_user.id)
        if user[currency] < bet:
            await message.answer(f"❌ Недостаточно средств. Баланс: {fmt_money(currency, user[currency])}")
            return
        
        update_balance(message.from_user.id, currency, -bet)
        
        win = random.choice([True, False])
        mult = 2.0 if win else 0
        payout = bet * mult if win else 0
        if win:
            update_balance(message.from_user.id, currency, payout)
        add_bet_record(message.from_user.id, bet, win, "diamond", currency)
        
        result_text = "ПОБЕДА 🎉" if win else "ПРОИГРЫШ 😔"
        
        await message.answer(
            f"💎 <b>Игра Алмазы</b>\n\n"
            f"🎲 Твой выбор: {choice}\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"💸 Выплата: {fmt_money(currency, payout)}\n"
            f"📊 Результат: <b>{result_text}</b>"
        )
    except:
        await message.answer("❌ Ошибка! Пример: `алмазы 100 gram diamond`", parse_mode="Markdown")

@dp.message(F.text.lower().startswith("башня"))
async def tower_text_cmd(message: Message):
    await message.answer("🗼 Игра Башня доступна только через кнопки в меню Игры!")
    await message.answer("🎮 Нажми 'Игры' → 'Башня'")

@dp.message(F.text.lower().startswith("кубик"))
async def cube_text_cmd(message: Message):
    if is_banned(message.from_user.id):
        await message.answer("❌ Вы забанены!")
        return
    
    if not can_play_game(message.from_user.id, "cube"):
        await message.answer("⏰ Подожди 3 секунды перед следующей игрой в Кубик!")
        return
    
    parts = message.text.lower().split()
    if len(parts) != 4:
        await message.answer("❌ Формат: `кубик 100 gram 5`", parse_mode="Markdown")
        return
    
    try:
        bet = float(parts[1])
        currency = parts[2]
        guess = int(parts[3])
        
        if currency not in ["gram", "gold"]:
            await message.answer("❌ Валюта должна быть 'gram' или 'gold'")
            return
        
        if guess < 1 or guess > 6:
            await message.answer("❌ Число должно быть от 1 до 6")
            return
        
        min_bet = MIN_BET_GRAM if currency == "gram" else MIN_BET_GOLD
        max_bet = MAX_BET_GRAM if currency == "gram" else MAX_BET_GOLD
        
        if bet < min_bet or bet > max_bet:
            await message.answer(f"❌ Ставка должна быть от {fmt_money(currency, min_bet)} до {fmt_money(currency, max_bet)}")
            return
        
        user = get_user(message.from_user.id)
        if user[currency] < bet:
            await message.answer(f"❌ Недостаточно средств. Баланс: {fmt_money(currency, user[currency])}")
            return
        
        win, mult, value = cube_play(guess)
        payout = bet * mult if win else 0
        
        update_balance(message.from_user.id, currency, -bet + payout)
        add_bet_record(message.from_user.id, bet, win, "cube", currency)
        
        result_text = "ПОБЕДА 🎉" if win else "ПРОИГРЫШ 😔"
        
        await message.answer(
            f"🎲 <b>Игра Кубик</b>\n\n"
            f"🎯 Твой выбор: <b>{guess}</b>\n"
            f"🎲 Выпало: <b>{value}</b>\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"💸 Выплата: {fmt_money(currency, payout)}\n"
            f"📊 Результат: <b>{result_text}</b>"
        )
    except:
        await message.answer("❌ Ошибка! Пример: `кубик 100 gram 5`", parse_mode="Markdown")

@dp.message(F.text.lower().startswith("кости"))
async def dice_text_cmd(message: Message):
    if is_banned(message.from_user.id):
        await message.answer("❌ Вы забанены!")
        return
    
    if not can_play_game(message.from_user.id, "dice"):
        await message.answer("⏰ Подожди 3 секунды перед следующей игрой в Кости!")
        return
    
    parts = message.text.lower().split()
    if len(parts) != 4:
        await message.answer("❌ Формат: `кости 100 gram больше`\nВарианты: больше, меньше, ровно", parse_mode="Markdown")
        return
    
    try:
        bet = float(parts[1])
        currency = parts[2]
        choice = parts[3]
        
        if currency not in ["gram", "gold"]:
            await message.answer("❌ Валюта должна быть 'gram' или 'gold'")
            return
        
        if choice not in ["больше", "меньше", "ровно"]:
            await message.answer("❌ Выбери: больше, меньше, ровно")
            return
        
        min_bet = MIN_BET_GRAM if currency == "gram" else MIN_BET_GOLD
        max_bet = MAX_BET_GRAM if currency == "gram" else MAX_BET_GOLD
        
        if bet < min_bet or bet > max_bet:
            await message.answer(f"❌ Ставка должна быть от {fmt_money(currency, min_bet)} до {fmt_money(currency, max_bet)}")
            return
        
        user = get_user(message.from_user.id)
        if user[currency] < bet:
            await message.answer(f"❌ Недостаточно средств. Баланс: {fmt_money(currency, user[currency])}")
            return
        
        win, mult, d1, d2, total = dice_play(choice)
        payout = bet * mult if win else 0
        
        update_balance(message.from_user.id, currency, -bet + payout)
        add_bet_record(message.from_user.id, bet, win, "dice", currency)
        
        result_text = "ПОБЕДА 🎉" if win else "ПРОИГРЫШ 😔"
        
        await message.answer(
            f"🎯 <b>Игра Кости</b>\n\n"
            f"🎲 Выпало: <b>{d1}</b> + <b>{d2}</b> = <b>{total}</b>\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"💸 Выплата: {fmt_money(currency, payout)}\n"
            f"📊 Результат: <b>{result_text}</b>"
        )
    except:
        await message.answer("❌ Ошибка! Пример: `кости 100 gram больше`", parse_mode="Markdown")

@dp.message(F.text.lower().startswith("футбол"))
async def football_text_cmd(message: Message):
    if is_banned(message.from_user.id):
        await message.answer("❌ Вы забанены!")
        return
    
    if not can_play_game(message.from_user.id, "football"):
        await message.answer("⏰ Подожди 3 секунды перед следующей игрой в Футбол!")
        return
    
    parts = message.text.lower().split()
    if len(parts) != 4:
        await message.answer("❌ Формат: `футбол 100 gram гол`\nВарианты: гол, мимо", parse_mode="Markdown")
        return
    
    try:
        bet = float(parts[1])
        currency = parts[2]
        choice = parts[3]
        
        if currency not in ["gram", "gold"]:
            await message.answer("❌ Валюта должна быть 'gram' или 'gold'")
            return
        
        if choice not in ["гол", "мимо"]:
            await message.answer("❌ Выбери: гол, мимо")
            return
        
        min_bet = MIN_BET_GRAM if currency == "gram" else MIN_BET_GOLD
        max_bet = MAX_BET_GRAM if currency == "gram" else MAX_BET_GOLD
        
        if bet < min_bet or bet > max_bet:
            await message.answer(f"❌ Ставка должна быть от {fmt_money(currency, min_bet)} до {fmt_money(currency, max_bet)}")
            return
        
        user = get_user(message.from_user.id)
        if user[currency] < bet:
            await message.answer(f"❌ Недостаточно средств. Баланс: {fmt_money(currency, user[currency])}")
            return
        
        win, mult, value = football_play(choice)
        payout = bet * mult if win else 0
        
        update_balance(message.from_user.id, currency, -bet + payout)
        add_bet_record(message.from_user.id, bet, win, "football", currency)
        
        outcome = "ГОЛ 🎉" if value >= 4 else "МИМО 😔"
        result_text = "ПОБЕДА 🎉" if win else "ПРОИГРЫШ 😔"
        
        await message.answer(
            f"⚽ <b>Игра Футбол</b>\n\n"
            f"🎲 Результат удара: <b>{outcome}</b> (значение {value})\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"💸 Выплата: {fmt_money(currency, payout)}\n"
            f"📊 Результат: <b>{result_text}</b>"
        )
    except:
        await message.answer("❌ Ошибка! Пример: `футбол 100 gram гол`", parse_mode="Markdown")

@dp.message(F.text.lower().startswith("баскет"))
async def basket_text_cmd(message: Message):
    if is_banned(message.from_user.id):
        await message.answer("❌ Вы забанены!")
        return
    
    if not can_play_game(message.from_user.id, "basket"):
        await message.answer("⏰ Подожди 3 секунды перед следующей игрой в Баскетбол!")
        return
    
    parts = message.text.lower().split()
    if len(parts) != 4:
        await message.answer("❌ Формат: `баскет 100 gold точный`\nВарианты: точный, промах", parse_mode="Markdown")
        return
    
    try:
        bet = float(parts[1])
        currency = parts[2]
        choice = parts[3]
        
        if currency not in ["gram", "gold"]:
            await message.answer("❌ Валюта должна быть 'gram' или 'gold'")
            return
        
        if choice not in ["точный", "промах"]:
            await message.answer("❌ Выбери: точный, промах")
            return
        
        min_bet = MIN_BET_GRAM if currency == "gram" else MIN_BET_GOLD
        max_bet = MAX_BET_GRAM if currency == "gram" else MAX_BET_GOLD
        
        if bet < min_bet or bet > max_bet:
            await message.answer(f"❌ Ставка должна быть от {fmt_money(currency, min_bet)} до {fmt_money(currency, max_bet)}")
            return
        
        user = get_user(message.from_user.id)
        if user[currency] < bet:
            await message.answer(f"❌ Недостаточно средств. Баланс: {fmt_money(currency, user[currency])}")
            return
        
        win, mult, value = basket_play(choice)
        payout = bet * mult if win else 0
        
        update_balance(message.from_user.id, currency, -bet + payout)
        add_bet_record(message.from_user.id, bet, win, "basket", currency)
        
        outcome = "ТОЧНЫЙ БРОСОК 🎉" if value in [4,5] else "ПРОМАХ 😔"
        result_text = "ПОБЕДА 🎉" if win else "ПРОИГРЫШ 😔"
        
        await message.answer(
            f"🏀 <b>Игра Баскетбол</b>\n\n"
            f"🎲 Результат броска: <b>{outcome}</b> (значение {value})\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"💸 Выплата: {fmt_money(currency, payout)}\n"
            f"📊 Результат: <b>{result_text}</b>"
        )
    except:
        await message.answer("❌ Ошибка! Пример: `баскет 100 gold точный`", parse_mode="Markdown")

@dp.message(Command("cancel"))
async def cancel_game(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id in active_games:
        active_games.pop(user_id)
        await message.answer("✅ Игра отменена.")
    elif user_id in active_tower_games:
        game = active_tower_games.pop(user_id)
        if game.get("level", 0) == 0:
            update_balance(user_id, game["currency"], game["bet"])
            await message.answer("✅ Игра отменена. Ставка возвращена на баланс.")
        else:
            await message.answer("✅ Игра отменена.")
    elif user_id in active_gold_games:
        game = active_gold_games.pop(user_id)
        if game.get("level", 0) == 0:
            update_balance(user_id, game["currency"], game["bet"])
            await message.answer("✅ Игра отменена. Ставка возвращена на баланс.")
        else:
            await message.answer("✅ Игра отменена.")
    elif user_id in active_diamond_games:
        game = active_diamond_games.pop(user_id)
        if not game.get("opened", False):
            update_balance(user_id, game["currency"], game["bet"])
            await message.answer("✅ Игра отменена. Ставка возвращена на баланс.")
        else:
            await message.answer("✅ Игра отменена.")
    else:
        await message.answer("❌ У вас нет активной игры.")
    await state.clear()

@dp.callback_query(F.data == "noop")
async def noop_callback(call: CallbackQuery):
    await call.answer()

# ========== ЗАПУСК ==========
async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Бот запущен!")
    print(f"⭐ Текущий курс Stars: 1 Star = {get_star_to_gold_rate()} Gold")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
