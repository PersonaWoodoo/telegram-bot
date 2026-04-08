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
)

# ========== КОНФИГ ==========
BOT_TOKEN = "8629137165:AAGN-d3ur1qJYiCmGB16HBgSjvcdZMPDK_A"
BOT_NAME = "WILLD GRAMM"
BOT_USERNAME = "WILLDGRAMM_bot"
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

# Лимиты ставок
MIN_BET_GRAM = 0.10
MAX_BET_GRAM = 100000.0
MIN_BET_GOLD = 0.01
MAX_BET_GOLD = 5000.0
MIN_WITHDRAW_GRAM = 75000.0
MIN_WITHDRAW_GOLD = 10.0

# Бонус
BONUS_GRAM_MIN = 0
BONUS_GRAM_MAX = 250

# ========== МНОЖИТЕЛИ ИГР ==========
FOOTBALL_MULTIPLIERS = {"gol": 1.4, "mimo": 1.6}
BASKET_MULTIPLIERS = {"tochniy": 1.4, "promah": 1.6}
CUBE_MULTIPLIERS = {"normal": 1.8, "three": 2.0}
GOLD_MULTIPLIERS = {"gold": 2.0, "silver": 1.5, "bronze": 1.2}  # Золото (вместо рулетки)
DIAMOND_MULTIPLIERS = {"diamond": 3.0, "ruby": 2.0, "emerald": 1.5}  # Алмазы (вместо краша)
DICE_MULTIPLIER = 3.5

# ========== СОЗДАЁМ DP ==========
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ========== БАЗА ДАННЫХ ==========
DB_PATH = "/app/casino.db" if os.path.exists("/app") else "casino.db"

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
            wallet TEXT,
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
    # Проверяем существует ли пользователь
    existing = conn.execute("SELECT * FROM users WHERE user_id = ?", (str(user_id),)).fetchone()
    
    if not existing:
        # Новый пользователь
        conn.execute("""
            INSERT INTO users (user_id, gram, gold, is_admin, registered_at, username, first_name, last_name, referrer_id) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (str(user_id), START_GRAM, START_GOLD, 1 if user_id in ADMIN_IDS else 0, now_ts(), username, first_name, last_name, str(referrer_id) if referrer_id else None))
        
        # Начисляем бонус рефереру
        if referrer_id and referrer_id != user_id:
            # 1500 грамм за регистрацию
            update_balance(referrer_id, "gram", 1500)
            conn.execute("UPDATE users SET referral_count = referral_count + 1, referral_earned = referral_earned + 1500 WHERE user_id = ?", (str(referrer_id),))
            conn.commit()
    else:
        # Обновляем информацию существующего
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

def update_balance(user_id: int, currency: str, delta: float) -> float:
    conn = get_db()
    conn.execute(f"UPDATE users SET {currency} = {currency} + ? WHERE user_id = ?", 
                 (round(delta, 2), str(user_id)))
    conn.commit()
    row = conn.execute(f"SELECT {currency} FROM users WHERE user_id = ?", (str(user_id),)).fetchone()
    conn.close()
    return row[currency]

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
    
    # Реферальные отчисления (1% с проигрыша друга)
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
    rows = conn.execute(f"SELECT user_id, {currency} FROM users WHERE is_banned = 0 ORDER BY {currency} DESC LIMIT ?", (limit,)).fetchall()
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
    total_withdrawn_gram = conn.execute("SELECT SUM(total_withdrawn_gram) FROM users").fetchone()[0] or 0
    total_withdrawn_gold = conn.execute("SELECT SUM(total_withdrawn_gold) FROM users").fetchone()[0] or 0
    conn.close()
    return {
        "total_users": total_users,
        "total_bets": total_bets,
        "total_wins": total_wins,
        "total_deposited_gram": total_deposited_gram,
        "total_deposited_gold": total_deposited_gold,
        "total_withdrawn_gram": total_withdrawn_gram,
        "total_withdrawn_gold": total_withdrawn_gold,
    }

# ========== ЗАЯВКИ НА ПОПОЛНЕНИЕ (с картинками) ==========
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

# ========== ЗАЯВКИ НА ВЫВОД ==========
def create_withdraw_request(user_id: int, currency: str, amount: float, wallet: str) -> int:
    conn = get_db()
    conn.execute('''
        INSERT INTO withdraw_requests (user_id, currency, amount, wallet, status, created_at)
        VALUES (?, ?, ?, ?, 'pending', ?)
    ''', (str(user_id), currency, amount, wallet, now_ts()))
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
        [InlineKeyboardButton(text="🧾 Чеки", callback_data="checks_menu"), InlineKeyboardButton(text="🎟 Промокод", callback_data="promo_menu")],
        [InlineKeyboardButton(text="🫶 Рефералы", callback_data="ref")]
    ]
    if is_admin(ADMIN_IDS[0]):
        kb.append([InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def games_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🥇 Золото", callback_data="game_gold"), InlineKeyboardButton(text="💎 Алмазы", callback_data="game_diamond")],
        [InlineKeyboardButton(text="🎲 Кубик", callback_data="game_cube"), InlineKeyboardButton(text="🎯 Кости", callback_data="game_dice")],
        [InlineKeyboardButton(text="⚽ Футбол", callback_data="game_football"), InlineKeyboardButton(text="🏀 Баскетбол", callback_data="game_basket")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

def admin_panel_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Все пользователи", callback_data="admin_all_users")],
        [InlineKeyboardButton(text="💰 Выдать валюту", callback_data="admin_give")],
        [InlineKeyboardButton(text="🔫 Забрать валюту", callback_data="admin_take")],
        [InlineKeyboardButton(text="👑 Выдать админа", callback_data="admin_set_admin")],
        [InlineKeyboardButton(text="👑 Снять админа", callback_data="admin_remove_admin")],
        [InlineKeyboardButton(text="🔒 Заблокировать", callback_data="admin_ban")],
        [InlineKeyboardButton(text="🔓 Разблокировать", callback_data="admin_unban")],
        [InlineKeyboardButton(text="📥 Заявки на вывод", callback_data="admin_withdraw_requests")],
        [InlineKeyboardButton(text="📤 Заявки на пополнение", callback_data="admin_deposit_requests")],
        [InlineKeyboardButton(text="📊 Статистика бота", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📜 Логи админов", callback_data="admin_logs")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🎟 Создать промокод", callback_data="admin_create_promo")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

def deposit_currency_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Пополнить Граммы", callback_data="deposit_gram")],
        [InlineKeyboardButton(text="🏅 Пополнить Iris-Gold", callback_data="deposit_gold")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
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
    waiting_choice = State()

class DepositStates(StatesGroup):
    waiting_currency = State()
    waiting_amount = State()
    waiting_screenshot = State()

class WithdrawStates(StatesGroup):
    waiting_currency = State()
    waiting_amount = State()
    waiting_wallet = State()

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

# Хранилище для КД пополнений (3 минуты)
last_deposit_time = {}

def can_deposit(user_id: int) -> bool:
    now = time.time()
    if user_id in last_deposit_time:
        if now - last_deposit_time[user_id] < 180:  # 3 минуты
            return False
    last_deposit_time[user_id] = now
    return True

# ========== ИГРЫ ==========
def gold_game(choice: str):
    """Золото: gold - x2, silver - x1.5, bronze - x1.2"""
    win = False
    mult = 0
    if choice == "gold":
        win, mult = True, GOLD_MULTIPLIERS["gold"]
    elif choice == "silver":
        win, mult = True, GOLD_MULTIPLIERS["silver"]
    elif choice == "bronze":
        win, mult = True, GOLD_MULTIPLIERS["bronze"]
    return win, mult

def diamond_game(choice: str):
    """Алмазы: diamond - x3, ruby - x2, emerald - x1.5"""
    win = False
    mult = 0
    if choice == "diamond":
        win, mult = True, DIAMOND_MULTIPLIERS["diamond"]
    elif choice == "ruby":
        win, mult = True, DIAMOND_MULTIPLIERS["ruby"]
    elif choice == "emerald":
        win, mult = True, DIAMOND_MULTIPLIERS["emerald"]
    return win, mult

# ========== ОСНОВНЫЕ ОБРАБОТЧИКИ ==========
@dp.message(CommandStart())
async def start_cmd(message: Message, bot: Bot):
    if is_banned(message.from_user.id):
        await message.answer("❌ Вы забанены и не можете использовать бота!")
        return
    
    # Обработка реферальной ссылки
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
    await message.answer(
        f"🌟 <b>Добро пожаловать в {BOT_NAME}!</b>\n\n"
        f"💰 <b>Твой баланс:</b>\n"
        f"💎 {GRAM_NAME}: {fmt_gram(user['gram'])}\n"
        f"🏅 {GOLD_NAME}: {fmt_gold(user['gold'])}\n\n"
        f"👇 Используй кнопки ниже или текстовые команды:\n\n"
        f"<b>📋 Доступные команды:</b>\n"
        f"• <code>б</code> или <code>баланс</code> - показать баланс\n"
        f"• <code>игры</code> - список игр\n"
        f"• <code>профиль</code> - твой профиль\n"
        f"• <code>топ</code> - топ игроков\n"
        f"• <code>бонус</code> - забрать бонус\n"
        f"• <code>чеки</code> - работа с чеками\n"
        f"• <code>промокод КОД</code> - активировать промокод\n"
        f"• <code>реф</code> - реферальная система\n\n"
        f"<b>🎮 Игры одной командой:</b>\n"
        f"• <code>золото 100 gram gold</code> (gold/silver/bronze)\n"
        f"• <code>алмазы 100 gram diamond</code> (diamond/ruby/emerald)\n"
        f"• <code>кубик 100 gram 5</code>\n"
        f"• <code>кости 100 gram больше</code>\n"
        f"• <code>футбол 100 gram гол</code>\n"
        f"• <code>баскет 100 gold точный</code>",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "check_subscribe")
async def check_subscribe_callback(call: CallbackQuery, bot: Bot):
    is_channel, is_chat = await check_all_subscriptions(call.from_user.id, bot)
    if is_channel and is_chat:
        await call.message.edit_text("✅ Подписка подтверждена! Теперь вы можете пользоваться ботом.", reply_markup=None)
        user = get_user(call.from_user.id)
        await call.message.answer(
            f"🌟 <b>Добро пожаловать в {BOT_NAME}!</b>\n\n"
            f"💰 Баланс:\n💎 {fmt_gram(user['gram'])}\n🏅 {fmt_gold(user['gold'])}",
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

# ========== РЕФЕРАЛЬНАЯ СИСТЕМА ==========
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

@dp.message(F.text.lower() == "игры")
async def games_text_cmd(message: Message):
    if is_banned(message.from_user.id):
        await message.answer("❌ Вы забанены!")
        return
    await message.answer(
        f"🎮 <b>Доступные игры</b>\n\n"
        f"<b>🥇 Золото</b> - выбери слиток\n"
        f"<code>золото 100 gram gold</code> (gold - x2, silver - x1.5, bronze - x1.2)\n\n"
        f"<b>💎 Алмазы</b> - выбери камень\n"
        f"<code>алмазы 100 gram diamond</code> (diamond - x3, ruby - x2, emerald - x1.5)\n\n"
        f"<b>🎲 Кубик</b> - угадай число\n"
        f"<code>кубик 100 gram 5</code>\n\n"
        f"<b>🎯 Кости</b> - угадай сумму\n"
        f"<code>кости 100 gram больше</code>\n"
        f"<code>кости 100 gram меньше</code>\n"
        f"<code>кости 100 gram ровно</code>\n\n"
        f"<b>⚽ Футбол</b> - удар по воротам\n"
        f"<code>футбол 100 gram гол</code>\n"
        f"<code>футбол 100 gram мимо</code>\n\n"
        f"<b>🏀 Баскетбол</b> - бросок\n"
        f"<code>баскет 100 gold точный</code>\n"
        f"<code>баскет 100 gold промах</code>"
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
    await message.answer(
        f"👤 <b>Профиль</b>\n\n"
        f"{mention_user(message.from_user.id, message.from_user.first_name)}, твоя статистика:\n\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n"
        f"📊 Статус: {admin_status}\n\n"
        f"💰 Баланс:\n💎 {fmt_gram(user['gram'])}\n🏅 {fmt_gold(user['gold'])}\n\n"
        f"📊 Статистика:\n"
        f"💎 Пополнено: {fmt_gram(user['total_deposited_gram'] or 0)}\n"
        f"🏅 Пополнено: {fmt_gold(user['total_deposited_gold'] or 0)}\n"
        f"📤 Выведено: {fmt_gram(user['total_withdrawn_gram'] or 0)} / {fmt_gold(user['total_withdrawn_gold'] or 0)}\n"
        f"🎲 Ставок: {bets} | Побед: {wins} ({wr:.1f}%)\n\n"
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
        text += f"{medal} {mention_user(int(p['user_id']))} — {fmt_gram(p['gram'])}\n"
    text += "\n🏅 <b>Iris-Gold:</b>\n"
    for i, p in enumerate(top_gold):
        medal = medals[i] if i < 3 else f"{i+1}."
        text += f"{medal} {mention_user(int(p['user_id']))} — {fmt_gold(p['gold'])}\n"
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

# ========== ИГРЫ ТЕКСТОВЫМИ КОМАНДАМИ ==========
@dp.message(lambda m: m.text and m.text.lower().startswith("золото"))
async def gold_text_cmd(message: Message):
    if is_banned(message.from_user.id):
        await message.answer("❌ Вы забанены!")
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
        
        win, mult = gold_game(choice)
        payout = bet * mult if win else 0
        if win:
            update_balance(message.from_user.id, currency, payout)
        add_bet_record(message.from_user.id, bet, win, "gold", currency)
        
        choice_names = {"gold": "🥇 Золотой слиток", "silver": "🥈 Серебряный слиток", "bronze": "🥉 Бронзовый слиток"}
        
        await message.answer(
            f"🥇 <b>Золото</b>\n\n"
            f"🎲 Твой выбор: {choice_names[choice]}\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"💸 Выплата: {fmt_money(currency, payout)}\n"
            f"📊 Результат: <b>{'ПОБЕДА 🎉' if win else 'ПРОИГРЫШ 😔'}</b>"
        )
    except:
        await message.answer("❌ Ошибка! Пример: `золото 100 gram gold`", parse_mode="Markdown")

@dp.message(lambda m: m.text and m.text.lower().startswith("алмазы"))
async def diamond_text_cmd(message: Message):
    if is_banned(message.from_user.id):
        await message.answer("❌ Вы забанены!")
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
        
        win, mult = diamond_game(choice)
        payout = bet * mult if win else 0
        if win:
            update_balance(message.from_user.id, currency, payout)
        add_bet_record(message.from_user.id, bet, win, "diamond", currency)
        
        choice_names = {"diamond": "💎 Алмаз", "ruby": "🔴 Рубин", "emerald": "🟢 Изумруд"}
        
        await message.answer(
            f"💎 <b>Алмазы</b>\n\n"
            f"🎲 Твой выбор: {choice_names[choice]}\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"💸 Выплата: {fmt_money(currency, payout)}\n"
            f"📊 Результат: <b>{'ПОБЕДА 🎉' if win else 'ПРОИГРЫШ 😔'}</b>"
        )
    except:
        await message.answer("❌ Ошибка! Пример: `алмазы 100 gram diamond`", parse_mode="Markdown")

@dp.message(lambda m: m.text and m.text.lower().startswith("кубик"))
async def cube_text_cmd(message: Message):
    if is_banned(message.from_user.id):
        await message.answer("❌ Вы забанены!")
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
        
        update_balance(message.from_user.id, currency, -bet)
        
        result = await message.answer_dice(emoji="🎲")
        value = result.dice.value
        win = guess == value
        mult = CUBE_MULTIPLIERS["three"] if guess == 3 else CUBE_MULTIPLIERS["normal"]
        payout = bet * mult if win else 0
        if win:
            update_balance(message.from_user.id, currency, payout)
        add_bet_record(message.from_user.id, bet, win, "cube", currency)
        
        await message.answer(
            f"🎲 <b>Кубик</b>\n\n"
            f"🎯 Твой выбор: <b>{guess}</b>\n"
            f"🎲 Выпало: <b>{value}</b>\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"💸 Выплата: {fmt_money(currency, payout)}\n"
            f"📊 Результат: <b>{'ПОБЕДА 🎉' if win else 'ПРОИГРЫШ 😔'}</b>"
        )
    except:
        await message.answer("❌ Ошибка! Пример: `кубик 100 gram 5`", parse_mode="Markdown")

@dp.message(lambda m: m.text and m.text.lower().startswith("кости"))
async def dice_text_cmd(message: Message):
    if is_banned(message.from_user.id):
        await message.answer("❌ Вы забанены!")
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
        
        update_balance(message.from_user.id, currency, -bet)
        
        d1 = await message.answer_dice(emoji="🎲")
        d2 = await message.answer_dice(emoji="🎲")
        total = d1.dice.value + d2.dice.value
        
        win = False
        if choice == "больше" and total > 7:
            win = True
        elif choice == "меньше" and total < 7:
            win = True
        elif choice == "ровно" and total == 7:
            win = True
        
        payout = bet * DICE_MULTIPLIER if win else 0
        if win:
            update_balance(message.from_user.id, currency, payout)
        add_bet_record(message.from_user.id, bet, win, "dice", currency)
        
        await message.answer(
            f"🎯 <b>Кости</b>\n\n"
            f"🎲 Выпало: <b>{d1.dice.value}</b> + <b>{d2.dice.value}</b> = <b>{total}</b>\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"💸 Выплата: {fmt_money(currency, payout)}\n"
            f"📊 Результат: <b>{'ПОБЕДА 🎉' if win else 'ПРОИГРЫШ 😔'}</b>"
        )
    except:
        await message.answer("❌ Ошибка! Пример: `кости 100 gram больше`", parse_mode="Markdown")

@dp.message(lambda m: m.text and m.text.lower().startswith("футбол"))
async def football_text_cmd(message: Message):
    if is_banned(message.from_user.id):
        await message.answer("❌ Вы забанены!")
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
        
        update_balance(message.from_user.id, currency, -bet)
        
        result = await message.answer_dice(emoji="⚽")
        value = result.dice.value
        win = (choice == "гол" and value >= 4) or (choice == "мимо" and value <= 3)
        mult = FOOTBALL_MULTIPLIERS["gol"] if (choice == "гол" and win) else FOOTBALL_MULTIPLIERS["mimo"] if win else 0
        payout = bet * mult if win else 0
        if win:
            update_balance(message.from_user.id, currency, payout)
        add_bet_record(message.from_user.id, bet, win, "football", currency)
        
        outcome = "ГОЛ 🎉" if value >= 4 else "МИМО 😔"
        await message.answer(
            f"⚽ <b>Футбол</b>\n\n"
            f"🎲 Результат: <b>{outcome}</b>\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"💸 Выплата: {fmt_money(currency, payout)}\n"
            f"📊 Результат: <b>{'ПОБЕДА 🎉' if win else 'ПРОИГРЫШ 😔'}</b>"
        )
    except:
        await message.answer("❌ Ошибка! Пример: `футбол 100 gram гол`", parse_mode="Markdown")

@dp.message(lambda m: m.text and m.text.lower().startswith("баскет"))
async def basket_text_cmd(message: Message):
    if is_banned(message.from_user.id):
        await message.answer("❌ Вы забанены!")
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
        
        update_balance(message.from_user.id, currency, -bet)
        
        result = await message.answer_dice(emoji="🏀")
        value = result.dice.value
        win = (choice == "точный" and value in [4, 5]) or (choice == "промах" and value not in [4, 5])
        mult = BASKET_MULTIPLIERS["tochniy"] if (choice == "точный" and win) else BASKET_MULTIPLIERS["promah"] if win else 0
        payout = bet * mult if win else 0
        if win:
            update_balance(message.from_user.id, currency, payout)
        add_bet_record(message.from_user.id, bet, win, "basket", currency)
        
        outcome = "ТОЧНЫЙ БРОСОК 🎉" if value in [4, 5] else "ПРОМАХ 😔"
        await message.answer(
            f"🏀 <b>Баскетбол</b>\n\n"
            f"🎲 Результат: <b>{outcome}</b>\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"💸 Выплата: {fmt_money(currency, payout)}\n"
            f"📊 Результат: <b>{'ПОБЕДА 🎉' if win else 'ПРОИГРЫШ 😔'}</b>"
        )
    except:
        await message.answer("❌ Ошибка! Пример: `баскет 100 gold точный`", parse_mode="Markdown")

@dp.message(Command("cancel"))
async def cancel_game(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id in active_games:
        game_data = active_games.pop(user_id)
        if game_data.get("bet") and not game_data.get("started"):
            update_balance(user_id, game_data["currency"], game_data["bet"])
            await message.answer("✅ Игра отменена. Ставка возвращена на баланс.")
        else:
            await message.answer("✅ Игра отменена.")
    else:
        await message.answer("❌ У вас нет активной игры.")
    await state.clear()

# ========== ПОПОЛНЕНИЕ (только через Stars, с КД 3 минуты) ==========
@dp.callback_query(F.data == "deposit")
async def deposit_start(call: CallbackQuery):
    await call.message.edit_text("💎 Выберите валюту для пополнения:", reply_markup=deposit_currency_menu())
    await call.answer()

@dp.callback_query(F.data == "deposit_gram")
async def deposit_gram(call: CallbackQuery, state: FSMContext):
    if not can_deposit(call.from_user.id):
        await call.answer("⏰ Вы можете пополнять баланс не чаще 1 раза в 3 минуты!", show_alert=True)
        return
    await state.update_data(currency="gram")
    await state.set_state(DepositStates.waiting_amount)
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
async def deposit_gold(call: CallbackQuery, state: FSMContext):
    if not can_deposit(call.from_user.id):
        await call.answer("⏰ Вы можете пополнять баланс не чаще 1 раза в 3 минуты!", show_alert=True)
        return
    await state.update_data(currency="gold")
    await state.set_state(DepositStates.waiting_amount)
    await call.message.edit_text(
        f"🏅 <b>Пополнение {GOLD_NAME}</b>\n\n"
        f"1️⃣ Переведите Gold на @{ADMIN_USERNAME}\n"
        f"2️⃣ Введите сумму, которую перевели (цифрами):\n\n"
        f"💰 Минимальная сумма: {fmt_gold(0.01)}\n\n"
        f"После ввода суммы пришлите скриншот перевода!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="deposit")]])
    )
    await call.answer()

@dp.message(DepositStates.waiting_amount)
async def deposit_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        if amount <= 0:
            await message.answer("❌ Сумма должна быть положительной!")
            return
        
        data = await state.get_data()
        currency = data["currency"]
        
        await state.update_data(amount=amount)
        await state.set_state(DepositStates.waiting_screenshot)
        
        await message.answer(
            f"📸 <b>Отправьте скриншот перевода</b>\n\n"
            f"💰 Сумма: {fmt_money(currency, amount)}\n"
            f"📤 Получатель: {'ID ' + str(ADMIN_IDS[0]) if currency == 'gram' else '@' + ADMIN_USERNAME}\n\n"
            f"После отправки скриншота администратор проверит перевод и пополнит баланс."
        )
    except:
        await message.answer("❌ Введите корректную сумму!")

@dp.message(DepositStates.waiting_screenshot, F.photo)
async def deposit_screenshot(message: Message, state: FSMContext):
    data = await state.get_data()
    currency = data["currency"]
    amount = data["amount"]
    
    # Сохраняем заявку
    req_id = create_deposit_request(message.from_user.id, currency, amount, message.photo[-1].file_id)
    
    await message.answer(
        f"✅ <b>Заявка на пополнение #{req_id} создана!</b>\n\n"
        f"💰 Сумма: {fmt_money(currency, amount)}\n"
        f"📸 Скриншот получен\n\n"
        f"⏳ Администратор проверит заявку в ближайшее время.",
        reply_markup=main_menu()
    )
    
    # Отправляем админам
    for admin_id in ADMIN_IDS:
        try:
            caption = (
                f"📥 <b>НОВАЯ ЗАЯВКА НА ПОПОЛНЕНИЕ</b>\n\n"
                f"👤 Пользователь: {mention_user(message.from_user.id, message.from_user.first_name)}\n"
                f"🆔 ID: <code>{message.from_user.id}</code>\n"
                f"💎 Валюта: {GRAM_NAME if currency == 'gram' else GOLD_NAME}\n"
                f"💰 Сумма: {fmt_money(currency, amount)}\n"
                f"🆔 Заявка: #{req_id}\n\n"
                f"✅ /approve_deposit {req_id} - подтвердить\n"
                f"❌ /decline_deposit {req_id} - отклонить"
            )
            await message.bot.send_photo(admin_id, photo=message.photo[-1].file_id, caption=caption)
        except:
            pass
    
    await state.clear()

@dp.message(DepositStates.waiting_screenshot)
async def deposit_screenshot_error(message: Message):
    await message.answer("❌ Пожалуйста, отправьте скриншот перевода (фото)!")

# ========== АДМИН-КОМАНДЫ ДЛЯ ЗАЯВОК НА ПОПОЛНЕНИЕ ==========
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
                # Начисляем рефереру 5% с доната
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
        text += f"{status} <code>{u['user_id']}</code> | 💎 {fmt_gram(u['gram'])} | 🏅 {fmt_gold(u['gold'])}\n"
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

@dp.message(AdminStates.waiting_user_id)
async def admin_get_user_id(message: Message, state: FSMContext):
    try:
        target_id = int(message.text)
        data = await state.get_data()
        action = data.get("action", "give")
        
        if action == "give":
            await state.update_data(target_id=target_id)
            await state.set_state(AdminStates.waiting_currency)
            await message.answer("💎 Введите валюту (gram или gold):")
        elif action == "take":
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
        text += f"🆔 #{r['id']} | {mention_user(int(r['user_id']))} | {fmt_money(r['currency'], r['amount'])} | {r['wallet']}\n"
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
    await call.message.edit_text(
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: {stats['total_users']}\n"
        f"🎲 Всего ставок: {stats['total_bets']}\n"
        f"🏆 Всего побед: {stats['total_wins']}\n"
        f"💎 Пополнено грамм: {fmt_gram(stats['total_deposited_gram'])}\n"
        f"🏅 Пополнено Gold: {fmt_gold(stats['total_deposited_gold'])}\n"
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

# ========== ВЫВОД ==========
@dp.callback_query(F.data == "withdraw")
async def withdraw_start(call: CallbackQuery):
    await call.message.edit_text("💰 Выберите валюту для вывода:", reply_markup=withdraw_menu())
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
        await state.set_state(WithdrawStates.waiting_wallet)
        await message.answer("💳 Введите реквизиты для вывода (кошелёк/карта):")
    except:
        await message.answer("❌ Введите число")

@dp.message(WithdrawStates.waiting_wallet)
async def withdraw_wallet_input(message: Message, state: FSMContext):
    wallet = message.text.strip()
    data = await state.get_data()
    currency = data["currency"]
    amount = data["amount"]
    req_id = create_withdraw_request(message.from_user.id, currency, amount, wallet)
    await message.answer(
        f"✅ Заявка на вывод #{req_id} создана!\n"
        f"Сумма: {fmt_money(currency, amount)}\n"
        f"Реквизиты: {wallet}\n"
        f"После проверки администратором средства будут отправлены.",
        reply_markup=main_menu()
    )
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                f"📤 <b>Заявка на вывод</b>\n"
                f"👤 {mention_user(message.from_user.id, message.from_user.first_name)}\n"
                f"💎 {GRAM_NAME if currency=='gram' else GOLD_NAME}: {fmt_money(currency, amount)}\n"
                f"📤 Кошелёк: {wallet}\n"
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
    await call.message.edit_text("🧾 Меню чеков:", reply_markup=checks_menu_kb())
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

# ========== АДМИН-КОМАНДЫ ДЛЯ ЗАЯВОК НА ВЫВОД ==========
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
            row = conn.execute("SELECT user_id, currency, amount FROM withdraw_requests WHERE id = ?", (req_id,)).fetchone()
            conn.close()
            if row:
                await message.bot.send_message(int(row["user_id"]), f"✅ Ваша заявка на вывод #{req_id} одобрена!\n💰 Сумма: {fmt_money(row['currency'], row['amount'])}")
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

# ========== ЗАПУСК ==========
active_games = {}

async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
