import telebot
import subprocess
import os
import zipfile
import tempfile
import shutil
from telebot import types
import time
from datetime import datetime, timedelta
import psutil
import sqlite3
import json
import logging
import threading
import re
import sys
import uuid
import atexit
import requests

# --- Flask Keep Alive ---
from flask import Flask

app = Flask('')

@app.route('/')
def home():
    return "I'm Marco File Host"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    print("Flask Keep-Alive started.")

# --- Configuration ---
TOKEN = os.getenv("BOT_TOKEN", "8851766777:AAEY80X1XXmX5xR1INnIqsOsHkdgJrpxX3U")
OWNER_ID = 8225743320
ADMIN_ID = 8225743320
YOUR_USERNAME = '@Junaid420'
UPDATE_CHANNEL = 'https://t.me/ZexDigitalMarketing'
UPDATE_CHANNEL_CHAT = 'https://t.me/ZexDigitalMarketing'

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_BOTS_DIR = os.path.join(BASE_DIR, 'upload_bots')
IROTECH_DIR = os.path.join(BASE_DIR, 'inf')
DATABASE_PATH = os.path.join(IROTECH_DIR, 'bot_data.db')
AUDIT_LOG_PATH = os.path.join(IROTECH_DIR, 'audit.log')

FREE_USER_LIMIT = 0
SUBSCRIBED_USER_LIMIT = 3
ADMIN_LIMIT = 999999
OWNER_LIMIT = float('inf')

os.makedirs(UPLOAD_BOTS_DIR, exist_ok=True)
os.makedirs(IROTECH_DIR, exist_ok=True)

bot = telebot.TeleBot(TOKEN)

# --- Runtime State ---
bot_scripts = {}
user_subscriptions = {}
user_files = {}
user_balances = {}
user_trials = {}
plans_data = {}
bot_settings = {}
banned_users = set()
user_last_seen = {}
system_settings = {
    "force_join": True,
    "deposit_enabled": True,
    "bot_locked": False,
    "trial_days": 0,
    "min_deposit": 20.0,
    "bkash_enabled": False,
    "bkash_number": "",
    "nagad_enabled": False,
    "nagad_number": "",
    "rocket_enabled": False,
    "rocket_number": "",
}
user_states = {}
active_users = set()
admin_ids = {ADMIN_ID, OWNER_ID}
pending_approvals = {}
pending_deposits = {}
BOT_START_TIME = datetime.now()

# --- Logging ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Premium Emojis ---
PEM = {
    "ok": '<tg-emoji emoji-id="6111726981760423576">✅</tg-emoji>',
    "no": '<tg-emoji emoji-id="6311965254817423602">❌</tg-emoji>',
    "warn": '<tg-emoji emoji-id="6314510813214284503">⚠️</tg-emoji>',
    "admin": '<tg-emoji emoji-id="5353032893096567467">📊</tg-emoji>',
    "user": '<tg-emoji emoji-id="5352861489541714456">👤</tg-emoji>',
    "money": '<tg-emoji emoji-id="6111799373434197692">💸</tg-emoji>',
    "msg": '<tg-emoji emoji-id="5337302974806922068">💬</tg-emoji>',
    "rocket": '<tg-emoji emoji-id="5352597830089347330">🚀</tg-emoji>',
    "pin": '<tg-emoji emoji-id="6111410240807245099">📌</tg-emoji>',
    "hi": '<tg-emoji emoji-id="5353027129250453493">👋</tg-emoji>',
    "add": '<tg-emoji emoji-id="6188038822509418008">➕</tg-emoji>',
    "rem": '<tg-emoji emoji-id="6188343249791358585">➖</tg-emoji>',
    "view": '<tg-emoji emoji-id="6188447235244562676">👀</tg-emoji>',
    "wait": '<tg-emoji emoji-id="6233136657722251031">⏳</tg-emoji>',
    "bell": '<tg-emoji emoji-id="6260082445018731350">🔔</tg-emoji>',
    "crown": '<tg-emoji emoji-id="6183661284467152997">👑</tg-emoji>',
    "gear": '<tg-emoji emoji-id="6260111633616475361">⚙️</tg-emoji>',
    "check": '<tg-emoji emoji-id="6188038822509418008">✅</tg-emoji>',
    "file": '<tg-emoji emoji-id="5352721946054268944">📁</tg-emoji>',
    "key": '<tg-emoji emoji-id="6233302765582424442">🔑</tg-emoji>',
    "join": '<tg-emoji emoji-id="5352597830089347330">➡️</tg-emoji>',
    "gift": '<tg-emoji emoji-id="6111799373434197692">🎁</tg-emoji>',
}

DB_LOCK = threading.Lock()

# --- Audit Log ---
def write_audit_log(actor_id, action_text):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] Actor={actor_id} | {action_text}\n"
    try:
        with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        logger.error(f"Audit log error: {e}")

# --- RAW API Helpers ---
def raw_send(chat_id, text, reply_keyboard=None, parse_mode="HTML"):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }
    if reply_keyboard:
        payload["reply_markup"] = {
            "keyboard": reply_keyboard,
            "resize_keyboard": True
        }
    try:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                          json=payload, timeout=60)
        return r.json()
    except Exception as e:
        logger.error(f"raw_send err: {e}")
        return {}

def rbtn(text, emoji_id=None, style=None):
    b = {"text": text}
    if emoji_id:
        b["icon_custom_emoji_id"] = emoji_id
    if style:
        b["style"] = style
    return b

# --- Keyboards ---
def get_main_kb(user_id):
    if user_id in admin_ids:
        return [
            [rbtn("💎 Plans", "6111799373434197692", "primary"),
             rbtn("👤 Profile", "5352861489541714456", "primary")],
            [rbtn("🤖 My Bots", "5352597830089347330", "success"),
             rbtn("💰 Deposit", "6111799373434197692", "success")],
            [rbtn("📢 Updates Channel", "5352597830089347330", "primary")],
            [rbtn("📤 Upload File", "5352721946054268944", "primary"),
             rbtn("📂 Check Files", "6188447235244562676", "primary")],
            [rbtn("⚡ Bot Speed", "6186175669991379791", "primary"),
             rbtn("📊 Statistics", "5353032893096567467", "success")],
            [rbtn("💳 Subscriptions", "6111799373434197692", "primary"),
             rbtn("📢 Broadcast", "5337302974806922068", "success")],
            [rbtn("🔒 Lock/Unlock", "6311965254817423602", "danger"),
             rbtn("🟢 Run All Code", "5352597830089347330", "success")],
            [rbtn("👑 Admin Panel", "6183661284467152997", "primary"),
             rbtn("📞 Contact Owner", "5337302974806922068", "primary")]
        ]
    else:
        return [
            [rbtn("💎 Plans", "6111799373434197692", "primary"),
             rbtn("👤 Profile", "5352861489541714456", "primary")],
            [rbtn("🤖 My Bots", "5352597830089347330", "success"),
             rbtn("💰 Deposit", "6111799373434197692", "success")],
            [rbtn("📢 Updates Channel", "5352597830089347330", "primary")],
            [rbtn("📤 Upload File", "5352721946054268944", "primary"),
             rbtn("📂 Check Files", "6188447235244562676", "primary")],
            [rbtn("⚡ Bot Speed", "6186175669991379791", "primary"),
             rbtn("📊 Statistics", "5353032893096567467", "success")],
            [rbtn("📞 Contact Owner", "5337302974806922068", "primary")]
        ]

def get_single_bot_kb(uid, fn):
    auto_on = is_auto_restart_enabled(uid, fn)
    auto_label = f"🔁 Auto-Restart: {'ON' if auto_on else 'OFF'} [{fn}]"
    return [
        [rbtn(f"🔄 Restart {fn}", "5352597830089347330", "primary"),
         rbtn(f"🛑 Stop {fn}", "6311965254817423602", "danger")],
        [rbtn(f"📜 Logs {fn}", "6188447235244562676", "primary"),
         rbtn(f"📊 Status {fn}", "5353032893096567467", "success")],
        [rbtn(auto_label, "6260111633616475361", "success" if auto_on else "primary")],
        [rbtn(f"📥 Download {fn}", "5352721946054268944", "primary"),
         rbtn(f"🧹 Clear Log {fn}", "6188343249791358585", "danger")],
        [rbtn(f"📦 Backup {fn}", "5352721946054268944", "primary"),
         rbtn(f"🗑️ Delete {fn}", "6311965254817423602", "danger")],
        [rbtn("🔙 Back", "6109360506319935223", "primary")]
    ]

def get_payment_setup_kb():
    bk_st = "ON" if system_settings["bkash_enabled"] else "OFF"
    ng_st = "ON" if system_settings["nagad_enabled"] else "OFF"
    rk_st = "ON" if system_settings["rocket_enabled"] else "OFF"
    dep_st = "ON" if system_settings["deposit_enabled"] else "OFF"
    return [
        [rbtn(f"bKash: {bk_st}", "6111799373434197692", "success" if system_settings["bkash_enabled"] else "danger"),
         rbtn(f"Nagad: {ng_st}", "6111799373434197692", "success" if system_settings["nagad_enabled"] else "danger")],
        [rbtn(f"Rocket: {rk_st}", "6111799373434197692", "success" if system_settings["rocket_enabled"] else "danger"),
         rbtn(f"Deposit System: {dep_st}", "6260111633616475361", "success" if system_settings["deposit_enabled"] else "danger")],
        [rbtn("✏️ Set bKash No", "6260111633616475361", "primary"),
         rbtn("✏️ Set Nagad No", "6260111633616475361", "primary")],
        [rbtn("✏️ Set Rocket No", "6260111633616475361", "primary"),
         rbtn("💵 Set Min Deposit", "6111799373434197692", "primary")],
        [rbtn("🔙 Back", "6109360506319935223", "primary")]
    ]

def get_system_toggles_kb():
    fj_st = "ON" if system_settings["force_join"] else "OFF"
    dp_st = "ON" if system_settings["deposit_enabled"] else "OFF"
    lk_st = "ON" if system_settings["bot_locked"] else "OFF"
    td = int(system_settings["trial_days"])
    return [
        [rbtn(f"📢 Force Join: {fj_st}", "5352597830089347330", "success" if system_settings["force_join"] else "danger"),
         rbtn(f"💰 Deposit: {dp_st}", "6111799373434197692", "success" if system_settings["deposit_enabled"] else "danger")],
        [rbtn(f"🔒 Lock Bot: {lk_st}", "6311965254817423602", "danger" if system_settings["bot_locked"] else "success"),
         rbtn(f"🎁 Trial Days: {td}d", "6111799373434197692", "primary")],
        [rbtn("✏️ Set Trial Days", "6260111633616475361", "primary")],
        [rbtn("🔙 Back", "6109360506319935223", "primary")]
    ]

OTHERS_OPTION_BUTTONS = [
    "💻 Server Stats", "🧠 RAM & CPU", "💾 Disk Usage", "🔄 Reboot Bot", "🛑 Stop All Bots",
    "🔁 Restart All Bots", "🧹 Clear Temp/Logs", "📋 Active Processes", "📦 Export DB JSON", "🩺 Health Check",
    "👥 Total Users", "🟢 Active Today", "🆕 New Users (7d)", "🚫 Ban User", "🔓 Unban User",
    "📋 Banned List", "💎 VIP Users List", "💰 Add Balance", "💸 Deduct Balance", "🔎 User Lookup",
    "📋 All Plans List", "🗑️ Delete Plan", "📁 All Hosted Files", "🔍 Search File", "📦 Zip All User Files",
    "⚠️ Error Logs Scan", "📊 Hosting Summary", "🔔 Test Admin Alert", "🧾 System Info", "📌 Quick Help"
]

def get_others_options_kb():
    rows = []
    for i in range(0, len(OTHERS_OPTION_BUTTONS), 2):
        pair = [rbtn(OTHERS_OPTION_BUTTONS[i], "6260111633616475361", "primary")]
        if i + 1 < len(OTHERS_OPTION_BUTTONS):
            pair.append(rbtn(OTHERS_OPTION_BUTTONS[i + 1], "6260111633616475361", "success" if (i // 2) % 2 == 1 else "primary"))
        rows.append(pair)
    rows.append([rbtn("🔙 Back", "6109360506319935223", "primary")])
    return rows

def get_admin_panel_kb(uid=None):
    rows = [
        [rbtn("🛠️ Plan Make", "6188038822509418008", "success"),
         rbtn("📥 Pending Deposits", "6233136657722251031", "primary")],
        [rbtn("💳 Payment Setup", "6111799373434197692", "primary"),
         rbtn("📜 Pay History", "6188447235244562676", "primary")],
        [rbtn("➕ ADD CHANNEL", "6188038822509418008", "success"),
         rbtn("➖ REMOVE CHANNEL", "6188343249791358585", "danger")],
        [rbtn("📦 Backup & Paste", "5352721946054268944", "primary"),
         rbtn("⚙️ System Toggles", "6260111633616475361", "primary")],
        [rbtn("📜 Plan History", "6188447235244562676", "primary"),
         rbtn("⚙️ Others Option", "6260111633616475361", "success")]
    ]
    if uid == OWNER_ID:
        rows.append([rbtn("🛡️ Audit Log", "6183661284467152997", "danger")])
    rows.append([rbtn("🔙 Back", "6109360506319935223", "primary")])
    return rows

# --- Safe Schema & Migration Helpers ---
def table_exists(conn, table_name):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    ).fetchone()
    return row is not None

def get_table_columns(conn, table_name):
    if not table_exists(conn, table_name):
        return []
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]

def ensure_columns(conn, table_name, col_defs):
    existing = set(get_table_columns(conn, table_name))
    for col_name, col_sql in col_defs.items():
        if col_name not in existing:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_sql}")

def rebuild_table_if_missing_key(conn, table_name, required_key_col, create_sql, copy_cols):
    if not table_exists(conn, table_name):
        conn.execute(create_sql)
        return
    cols = get_table_columns(conn, table_name)
    if required_key_col not in cols:
        bak_name = f"{table_name}_legacy_{int(time.time())}"
        conn.execute(f"ALTER TABLE {table_name} RENAME TO {bak_name}")
        conn.execute(create_sql)
        common = [c for c in copy_cols if c in get_table_columns(conn, bak_name)]
        if common:
            col_list = ", ".join(common)
            conn.execute(f"INSERT OR IGNORE INTO {table_name} ({col_list}) SELECT {col_list} FROM {bak_name}")

def init_db():
    with DB_LOCK:
        try:
            conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
            c = conn.cursor()

            c.execute('CREATE TABLE IF NOT EXISTS subscriptions (user_id INTEGER PRIMARY KEY, expiry TEXT)')
            ensure_columns(conn, 'subscriptions', {'expiry': 'TEXT'})

            c.execute('CREATE TABLE IF NOT EXISTS user_files (user_id INTEGER, file_name TEXT, file_type TEXT, PRIMARY KEY (user_id, file_name))')
            ensure_columns(conn, 'user_files', {'file_type': 'TEXT'})

            c.execute('CREATE TABLE IF NOT EXISTS active_users (user_id INTEGER PRIMARY KEY, joined_at TEXT, last_seen TEXT)')
            ensure_columns(conn, 'active_users', {'joined_at': 'TEXT', 'last_seen': 'TEXT'})

            c.execute('CREATE TABLE IF NOT EXISTS banned_users (user_id INTEGER PRIMARY KEY, reason TEXT)')
            c.execute('CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)')
            c.execute('CREATE TABLE IF NOT EXISTS force_channels (chat_id TEXT PRIMARY KEY, title TEXT, invite_link TEXT)')
            ensure_columns(conn, 'force_channels', {'title': 'TEXT', 'invite_link': 'TEXT'})

            c.execute('CREATE TABLE IF NOT EXISTS user_balances (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0.0)')
            ensure_columns(conn, 'user_balances', {'balance': 'REAL DEFAULT 0.0'})

            c.execute('CREATE TABLE IF NOT EXISTS user_trials (user_id INTEGER PRIMARY KEY, trial_used INTEGER DEFAULT 0, trial_expiry TEXT)')
            ensure_columns(conn, 'user_trials', {'trial_used': 'INTEGER DEFAULT 0', 'trial_expiry': 'TEXT'})

            plans_create = '''CREATE TABLE IF NOT EXISTS plans (
                code TEXT PRIMARY KEY, name TEXT, file_limit INTEGER, days INTEGER, price REAL
            )'''
            rebuild_table_if_missing_key(
                conn, 'plans', 'code', plans_create,
                ['code', 'name', 'file_limit', 'days', 'price']
            )
            ensure_columns(conn, 'plans', {
                'name': 'TEXT', 'file_limit': 'INTEGER DEFAULT 1',
                'days': 'INTEGER DEFAULT 30', 'price': 'REAL DEFAULT 0.0'
            })

            c.execute('''CREATE TABLE IF NOT EXISTS plan_orders (
                order_id TEXT PRIMARY KEY, user_id INTEGER, plan_code TEXT, plan_name TEXT,
                days INTEGER, file_limit INTEGER, price REAL, source TEXT, created_at TEXT
            )''')
            ensure_columns(conn, 'plan_orders', {
                'user_id': 'INTEGER', 'plan_code': 'TEXT', 'plan_name': 'TEXT',
                'days': 'INTEGER DEFAULT 0', 'file_limit': 'INTEGER DEFAULT 0',
                'price': 'REAL DEFAULT 0.0', 'source': 'TEXT', 'created_at': 'TEXT'
            })

            deposits_create = '''CREATE TABLE IF NOT EXISTS deposits (
                deposit_id TEXT PRIMARY KEY, user_id INTEGER, username TEXT, method TEXT,
                amount REAL, trx_id TEXT, status TEXT, created_at TEXT
            )'''
            rebuild_table_if_missing_key(
                conn, 'deposits', 'deposit_id', deposits_create,
                ['deposit_id', 'user_id', 'username', 'method', 'amount', 'trx_id', 'status', 'created_at']
            )
            ensure_columns(conn, 'deposits', {
                'user_id': 'INTEGER', 'username': 'TEXT', 'method': 'TEXT',
                'amount': 'REAL DEFAULT 0.0', 'trx_id': 'TEXT',
                'status': 'TEXT DEFAULT "pending"', 'created_at': 'TEXT'
            })

            c.execute('''CREATE TABLE IF NOT EXISTS bot_settings (
                user_id INTEGER, file_name TEXT, auto_restart INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, file_name)
            )''')
            ensure_columns(conn, 'bot_settings', {'auto_restart': 'INTEGER DEFAULT 0'})

            c.execute('CREATE TABLE IF NOT EXISTS system_settings (key TEXT PRIMARY KEY, value TEXT)')
            ensure_columns(conn, 'system_settings', {'value': 'TEXT'})

            c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (OWNER_ID,))
            if ADMIN_ID != OWNER_ID:
                c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (ADMIN_ID,))
            conn.commit()
            conn.close()
            logger.info("DB OK & migrated.")
        except Exception as e:
            logger.error(f"DB err: {e}", exc_info=True)

def save_system_setting_db(key, value):
    system_settings[key] = value
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        try:
            conn.execute('INSERT OR REPLACE INTO system_settings (key, value) VALUES (?, ?)',
                         (str(key), json.dumps(value)))
            conn.commit()
        finally:
            conn.close()

def touch_user_activity(uid, is_new=False):
    now_str = datetime.now().isoformat()
    active_users.add(uid)
    user_last_seen[uid] = now_str
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        try:
            if is_new:
                conn.execute('INSERT OR IGNORE INTO active_users (user_id, joined_at, last_seen) VALUES (?, ?, ?)',
                             (uid, now_str, now_str))
            else:
                conn.execute('INSERT OR IGNORE INTO active_users (user_id, joined_at, last_seen) VALUES (?, ?, ?)',
                             (uid, now_str, now_str))
            conn.execute('UPDATE active_users SET last_seen = ? WHERE user_id = ?', (now_str, uid))
            conn.commit()
        finally:
            conn.close()

def load_data():
    global bot_locked
    with DB_LOCK:
        try:
            conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
            c = conn.cursor()

            user_subscriptions.clear()
            c.execute('SELECT user_id, expiry FROM subscriptions')
            for u, e in c.fetchall():
                try:
                    if e:
                        user_subscriptions[u] = {'expiry': datetime.fromisoformat(e)}
                except Exception:
                    pass

            user_files.clear()
            c.execute('SELECT user_id, file_name, file_type FROM user_files')
            for u, fn, ft in c.fetchall():
                user_files.setdefault(u, []).append((fn, ft or 'py'))

            c.execute('SELECT user_id, last_seen FROM active_users')
            for x, ls in c.fetchall():
                active_users.add(x)
                if ls:
                    user_last_seen[x] = ls

            banned_users.clear()
            c.execute('SELECT user_id FROM banned_users')
            banned_users.update(x for (x,) in c.fetchall())

            c.execute('SELECT user_id FROM admins')
            admin_ids.update(x for (x,) in c.fetchall())

            user_balances.clear()
            c.execute('SELECT user_id, balance FROM user_balances')
            for u, bal in c.fetchall():
                user_balances[u] = float(bal or 0.0)

            user_trials.clear()
            c.execute('SELECT user_id, trial_used, trial_expiry FROM user_trials')
            for u, tu, te in c.fetchall():
                exp_dt = None
                if te:
                    try:
                        exp_dt = datetime.fromisoformat(te)
                    except Exception:
                        exp_dt = None
                user_trials[u] = {"used": bool(tu), "expiry": exp_dt}

            plans_data.clear()
            p_cols = set(get_table_columns(conn, 'plans'))
            if 'code' in p_cols:
                c.execute('SELECT code, name, file_limit, days, price FROM plans')
                for code, name, fl, days, price in c.fetchall():
                    if code:
                        plans_data[code] = {
                            "code": code, "name": name or code,
                            "file_limit": int(fl or 1),
                            "days": int(days or 30),
                            "price": float(price or 0.0)
                        }

            bot_settings.clear()
            c.execute('SELECT user_id, file_name, auto_restart FROM bot_settings')
            for u, fn, ar in c.fetchall():
                bot_settings[f"{u}_{fn}"] = {"auto_restart": bool(ar)}

            c.execute('SELECT key, value FROM system_settings')
            for k, v in c.fetchall():
                if k in system_settings and v is not None:
                    try:
                        system_settings[k] = json.loads(v)
                    except Exception:
                        system_settings[k] = v

            pending_deposits.clear()
            d_cols = set(get_table_columns(conn, 'deposits'))
            if 'deposit_id' in d_cols:
                c.execute('SELECT deposit_id, user_id, username, method, amount, trx_id, status, created_at FROM deposits WHERE status = "pending"')
                for did, u, un, meth, amt, trx, st, ca in c.fetchall():
                    if did:
                        pending_deposits[did] = {
                            "deposit_id": did, "user_id": u, "username": un,
                            "method": meth, "amount": float(amt or 0.0), "trx_id": trx,
                            "status": st, "created_at": ca
                        }

            bot_locked = bool(system_settings.get("bot_locked", False))
            conn.close()
            logger.info(f"Loaded: {len(active_users)} users, {len(plans_data)} plans, {len(pending_deposits)} pending deposits")
        except Exception as e:
            logger.error(f"Load err: {e}", exc_info=True)

init_db()
load_data()

# --- DB Operations ---
def get_balance(uid):
    return float(user_balances.get(uid, 0.0))

def set_balance_db(uid, amount):
    amount = round(float(amount), 2)
    user_balances[uid] = amount
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        try:
            conn.execute('INSERT OR REPLACE INTO user_balances (user_id, balance) VALUES (?, ?)', (uid, amount))
            conn.commit()
        finally:
            conn.close()

def add_balance_db(uid, delta):
    new_bal = round(get_balance(uid) + float(delta), 2)
    set_balance_db(uid, new_bal)
    return new_bal

def ban_user_db(uid, reason="Banned by admin"):
    if uid == OWNER_ID:
        return False
    banned_users.add(uid)
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        try:
            conn.execute('INSERT OR REPLACE INTO banned_users (user_id, reason) VALUES (?, ?)', (uid, reason))
            conn.commit()
            return True
        finally:
            conn.close()

def unban_user_db(uid):
    banned_users.discard(uid)
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        try:
            cur = conn.execute('DELETE FROM banned_users WHERE user_id = ?', (uid,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

def delete_plan_db(code):
    plans_data.pop(code, None)
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        try:
            cur = conn.execute('DELETE FROM plans WHERE code = ?', (code,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

def save_plan_db(code, name, file_limit, days, price):
    plans_data[code] = {
        "code": code, "name": name, "file_limit": int(file_limit),
        "days": int(days), "price": float(price)
    }
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        try:
            conn.execute('''INSERT OR REPLACE INTO plans (code, name, file_limit, days, price)
                            VALUES (?, ?, ?, ?, ?)''',
                         (code, name, int(file_limit), int(days), float(price)))
            conn.commit()
        finally:
            conn.close()

def save_plan_order_db(order_id, uid, plan_code, plan_name, days, file_limit, price, source="balance"):
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        try:
            conn.execute('''INSERT INTO plan_orders
                            (order_id, user_id, plan_code, plan_name, days, file_limit, price, source, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                         (order_id, uid, plan_code, plan_name, int(days), int(file_limit), float(price), source, created_at))
            conn.commit()
        finally:
            conn.close()

def save_deposit_db(dep):
    pending_deposits[dep["deposit_id"]] = dep
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        try:
            conn.execute('''INSERT OR REPLACE INTO deposits
                            (deposit_id, user_id, username, method, amount, trx_id, status, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                         (dep["deposit_id"], dep["user_id"], dep.get("username", ""),
                          dep["method"], float(dep["amount"]), dep["trx_id"],
                          dep["status"], dep["created_at"]))
            conn.commit()
        finally:
            conn.close()

def update_deposit_status_db(dep_id, status):
    if dep_id in pending_deposits:
        pending_deposits[dep_id]["status"] = status
        if status != "pending":
            pending_deposits.pop(dep_id, None)
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        try:
            conn.execute('UPDATE deposits SET status = ? WHERE deposit_id = ?', (status, dep_id))
            conn.commit()
        finally:
            conn.close()

def is_auto_restart_enabled(uid, fn):
    return bool(bot_settings.get(f"{uid}_{fn}", {}).get("auto_restart", False))

def set_auto_restart_db(uid, fn, enabled):
    enabled = bool(enabled)
    bot_settings[f"{uid}_{fn}"] = {"auto_restart": enabled}
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        try:
            conn.execute('''INSERT OR REPLACE INTO bot_settings (user_id, file_name, auto_restart)
                            VALUES (?, ?, ?)''', (uid, fn, 1 if enabled else 0))
            conn.commit()
        finally:
            conn.close()

def grant_trial_if_available(uid):
    td = int(system_settings.get("trial_days", 0) or 0)
    if td <= 0 or uid in admin_ids:
        return False
    tr = user_trials.get(uid)
    if tr and tr.get("used"):
        return False
    exp = datetime.now() + timedelta(days=td)
    user_trials[uid] = {"used": True, "expiry": exp}
    save_subscription(uid, exp)
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        try:
            conn.execute('''INSERT OR REPLACE INTO user_trials (user_id, trial_used, trial_expiry)
                            VALUES (?, 1, ?)''', (uid, exp.isoformat()))
            conn.commit()
        finally:
            conn.close()
    return True

def get_active_plan_limit(uid):
    now = datetime.now()
    if uid in user_subscriptions:
        exp = user_subscriptions[uid].get('expiry')
        if exp and exp > now:
            lim = user_subscriptions[uid].get('file_limit', SUBSCRIBED_USER_LIMIT)
            return max(SUBSCRIBED_USER_LIMIT, int(lim))
    tr = user_trials.get(uid)
    if tr and tr.get("expiry") and tr["expiry"] > now:
        return SUBSCRIBED_USER_LIMIT
    return FREE_USER_LIMIT

def get_user_folder(uid):
    f = os.path.join(UPLOAD_BOTS_DIR, str(uid))
    os.makedirs(f, exist_ok=True)
    return f

def get_user_file_limit(uid):
    if uid == OWNER_ID:
        return OWNER_LIMIT
    if uid in admin_ids:
        return ADMIN_LIMIT
    return get_active_plan_limit(uid)

def get_user_file_count(uid):
    return len(user_files.get(uid, []))

# --- Process Control & Live Stats ---
def is_bot_running(owner, fn):
    key = f"{owner}_{fn}"
    info = bot_scripts.get(key)
    if info and info.get('process'):
        try:
            p = psutil.Process(info['process'].pid)
            r = p.is_running() and p.status() != psutil.STATUS_ZOMBIE
            if not r:
                if 'log_file' in info and hasattr(info['log_file'], 'close') and not info['log_file'].closed:
                    try:
                        info['log_file'].close()
                    except Exception:
                        pass
                bot_scripts.pop(key, None)
            return r
        except psutil.NoSuchProcess:
            if 'log_file' in info and hasattr(info['log_file'], 'close') and not info['log_file'].closed:
                try:
                    info['log_file'].close()
                except Exception:
                    pass
            bot_scripts.pop(key, None)
            return False
        except Exception:
            return False
    return False

def get_bot_live_metrics(owner, fn):
    key = f"{owner}_{fn}"
    info = bot_scripts.get(key)
    running = is_bot_running(owner, fn)
    if not running or not info or not info.get('process'):
        return {
            "running": False, "pid": "N/A", "ram_mb": 0.0,
            "cpu_pct": 0.0, "uptime": "0s"
        }
    pid = info['process'].pid
    ram_mb = 0.0
    cpu_pct = 0.0
    try:
        p = psutil.Process(pid)
        rss = p.memory_info().rss
        cpu_pct = p.cpu_percent(interval=0.1)
        for ch in p.children(recursive=True):
            try:
                rss += ch.memory_info().rss
                cpu_pct += ch.cpu_percent(interval=0.0)
            except Exception:
                pass
        ram_mb = round(rss / (1024 * 1024), 2)
    except Exception:
        pass

    st = info.get('start_time')
    if isinstance(st, datetime):
        sec = int((datetime.now() - st).total_seconds())
        days, rem = divmod(sec, 86400)
        hrs, rem = divmod(rem, 3600)
        mins, secs = divmod(rem, 60)
        if days > 0:
            uptime = f"{days}d {hrs}h {mins}m"
        elif hrs > 0:
            uptime = f"{hrs}h {mins}m {secs}s"
        else:
            uptime = f"{mins}m {secs}s"
    else:
        uptime = "N/A"

    return {
        "running": True, "pid": pid, "ram_mb": ram_mb,
        "cpu_pct": round(cpu_pct, 1), "uptime": uptime
    }

def kill_process_tree(info):
    try:
        if 'log_file' in info and hasattr(info['log_file'], 'close') and not info['log_file'].closed:
            try:
                info['log_file'].close()
            except Exception:
                pass
        p = info.get('process')
        if p and hasattr(p, 'pid'):
            pid = p.pid
            if pid:
                try:
                    parent = psutil.Process(pid)
                    children = parent.children(recursive=True)
                    for ch in children:
                        try:
                            ch.terminate()
                        except Exception:
                            try:
                                ch.kill()
                            except Exception:
                                pass
                    gone, alive = psutil.wait_procs(children, timeout=1)
                    for x in alive:
                        try:
                            x.kill()
                        except Exception:
                            pass
                    try:
                        parent.terminate()
                        try:
                            parent.wait(timeout=1)
                        except psutil.TimeoutExpired:
                            parent.kill()
                    except psutil.NoSuchProcess:
                        pass
                    except Exception:
                        try:
                            parent.kill()
                        except Exception:
                            pass
                except psutil.NoSuchProcess:
                    pass
    except Exception as e:
        logger.error(f"kill err: {e}")

# --- Auto Install ---
TELEGRAM_MODULES = {
    'telebot': 'pyTelegramBotAPI', 'telegram': 'python-telegram-bot',
    'aiogram': 'aiogram', 'pyrogram': 'pyrogram', 'telethon': 'telethon',
    'requests': 'requests', 'bs4': 'beautifulsoup4', 'pillow': 'Pillow',
    'cv2': 'opencv-python', 'yaml': 'PyYAML', 'dotenv': 'python-dotenv',
    'pandas': 'pandas', 'numpy': 'numpy', 'flask': 'Flask',
    'psutil': 'psutil', 'uuid': None, 'asyncio': None, 'json': None,
    'datetime': None, 'os': None, 'sys': None, 're': None, 'time': None,
    'math': None, 'random': None, 'logging': None, 'threading': None,
    'subprocess': None, 'zipfile': None, 'tempfile': None, 'shutil': None,
    'sqlite3': None, 'atexit': None
}

def attempt_install_pip(mod, msg):
    pkg = TELEGRAM_MODULES.get(mod.lower(), mod)
    if pkg is None:
        return False
    try:
        if msg:
            bot.reply_to(msg, f"🐍 Installing `{pkg}`...", parse_mode='Markdown')
        r = subprocess.run([sys.executable, '-m', 'pip', 'install', pkg],
                           capture_output=True, text=True, check=False,
                           encoding='utf-8', errors='ignore')
        if r.returncode == 0:
            if msg:
                bot.reply_to(msg, f"{PEM['ok']} Installed `{pkg}`.", parse_mode='HTML')
            return True
        else:
            if msg:
                err = f"{PEM['no']} Failed.\n<pre>{r.stderr or r.stdout}</pre>"
                if len(err) > 4000:
                    err = err[:4000] + "\n..."
                bot.reply_to(msg, err, parse_mode='HTML')
            return False
    except Exception as e:
        if msg:
            bot.reply_to(msg, f"{PEM['no']} Error: {e}", parse_mode='HTML')
        return False

def attempt_install_npm(mod, folder, msg):
    try:
        if msg:
            bot.reply_to(msg, f"🟠 Installing npm `{mod}`...")
        r = subprocess.run(['npm', 'install', mod], capture_output=True, text=True,
                           check=False, cwd=folder, encoding='utf-8', errors='ignore')
        if r.returncode == 0:
            if msg:
                bot.reply_to(msg, f"{PEM['ok']} npm `{mod}` installed.", parse_mode='HTML')
            return True
        else:
            if msg:
                err = f"{PEM['no']} npm failed.\n<pre>{r.stderr or r.stdout}</pre>"
                if len(err) > 4000:
                    err = err[:4000] + "\n..."
                bot.reply_to(msg, err, parse_mode='HTML')
            return False
    except FileNotFoundError:
        if msg:
            bot.reply_to(msg, f"{PEM['no']} 'npm' not found.", parse_mode='HTML')
        return False
    except Exception as e:
        if msg:
            bot.reply_to(msg, f"{PEM['no']} Error: {e}", parse_mode='HTML')
        return False

# --- Run Scripts ---
def run_script(path, owner, folder, fn, msg_obj, attempt=1, silent=False):
    max_attempts = 2
    if attempt > max_attempts:
        if not silent and msg_obj:
            bot.reply_to(msg_obj, f"{PEM['no']} Failed after {max_attempts} attempts.", parse_mode='HTML')
        return
    key = f"{owner}_{fn}"
    try:
        if not os.path.exists(path):
            if not silent and msg_obj:
                bot.reply_to(msg_obj, f"{PEM['no']} Script not found.", parse_mode='HTML')
            if owner in user_files:
                user_files[owner] = [f for f in user_files.get(owner, []) if f[0] != fn]
            remove_user_file_db(owner, fn)
            return
        if attempt == 1:
            cp = None
            try:
                cp = subprocess.Popen([sys.executable, path], cwd=folder,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      text=True, encoding='utf-8', errors='ignore')
                out, err = cp.communicate(timeout=5)
                rc = cp.returncode
                if rc != 0 and err:
                    m = re.search(r"ModuleNotFoundError: No module named '(.+?)'", err)
                    if m:
                        mod = m.group(1).strip().strip("'\"")
                        if attempt_install_pip(mod, msg_obj):
                            if not silent and msg_obj:
                                bot.reply_to(msg_obj, f"{PEM['wait']} Retrying...", parse_mode='HTML')
                            time.sleep(2)
                            threading.Thread(target=run_script, args=(path, owner, folder, fn, msg_obj, attempt + 1, silent)).start()
                            return
                        return
                    else:
                        if not silent and msg_obj:
                            bot.reply_to(msg_obj, f"{PEM['no']} Error:\n<pre>{err[:500]}</pre>", parse_mode='HTML')
                        return
            except subprocess.TimeoutExpired:
                if cp and cp.poll() is None:
                    cp.kill()
                    cp.communicate()
            except FileNotFoundError:
                if not silent and msg_obj:
                    bot.reply_to(msg_obj, f"{PEM['no']} Python not found.", parse_mode='HTML')
                return
            except Exception as e:
                if not silent and msg_obj:
                    bot.reply_to(msg_obj, f"{PEM['no']} Error: {e}", parse_mode='HTML')
                return
            finally:
                if cp and cp.poll() is None:
                    cp.kill()
                    cp.communicate()

        log_path = os.path.join(folder, f"{os.path.splitext(fn)[0]}.log")
        lf = None
        pr = None
        try:
            lf = open(log_path, 'w', encoding='utf-8', errors='ignore')
        except Exception as e:
            if not silent and msg_obj:
                bot.reply_to(msg_obj, f"{PEM['no']} Log open failed: {e}", parse_mode='HTML')
            return
        try:
            si = None
            cf = 0
            if os.name == 'nt':
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = subprocess.SW_HIDE
            pr = subprocess.Popen([sys.executable, path], cwd=folder,
                                  stdout=lf, stderr=lf, stdin=subprocess.PIPE,
                                  startupinfo=si, creationflags=cf,
                                  encoding='utf-8', errors='ignore')
            chat_id = msg_obj.chat.id if msg_obj else owner
            bot_scripts[key] = {
                'process': pr, 'log_file': lf, 'file_name': fn,
                'chat_id': chat_id, 'script_owner_id': owner,
                'start_time': datetime.now(), 'user_folder': folder,
                'type': 'py', 'script_key': key
            }
            if not silent and msg_obj:
                bot.reply_to(msg_obj, f"{PEM['ok']} Python script '{fn}' started! (PID: {pr.pid})", parse_mode='HTML')
        except FileNotFoundError:
            if lf and not lf.closed:
                lf.close()
            if not silent and msg_obj:
                bot.reply_to(msg_obj, f"{PEM['no']} Python not found.", parse_mode='HTML')
            bot_scripts.pop(key, None)
        except Exception as e:
            if lf and not lf.closed:
                lf.close()
            if not silent and msg_obj:
                bot.reply_to(msg_obj, f"{PEM['no']} Error: {e}", parse_mode='HTML')
            if pr and pr.poll() is None:
                kill_process_tree({'process': pr, 'log_file': lf, 'script_key': key})
            bot_scripts.pop(key, None)
    except Exception as e:
        if not silent and msg_obj:
            bot.reply_to(msg_obj, f"{PEM['no']} Error: {e}", parse_mode='HTML')
        if key in bot_scripts:
            kill_process_tree(bot_scripts[key])
            del bot_scripts[key]

def run_js_script(path, owner, folder, fn, msg_obj, attempt=1, silent=False):
    max_attempts = 2
    if attempt > max_attempts:
        if not silent and msg_obj:
            bot.reply_to(msg_obj, f"{PEM['no']} Failed after {max_attempts} attempts.", parse_mode='HTML')
        return
    key = f"{owner}_{fn}"
    try:
        if not os.path.exists(path):
            if not silent and msg_obj:
                bot.reply_to(msg_obj, f"{PEM['no']} Script not found.", parse_mode='HTML')
            if owner in user_files:
                user_files[owner] = [f for f in user_files.get(owner, []) if f[0] != fn]
            remove_user_file_db(owner, fn)
            return
        if attempt == 1:
            cp = None
            try:
                cp = subprocess.Popen(['node', path], cwd=folder,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      text=True, encoding='utf-8', errors='ignore')
                out, err = cp.communicate(timeout=5)
                rc = cp.returncode
                if rc != 0 and err:
                    m = re.search(r"Cannot find module '(.+?)'", err)
                    if m:
                        mod = m.group(1).strip().strip("'\"")
                        if not mod.startswith('.') and not mod.startswith('/'):
                            if attempt_install_npm(mod, folder, msg_obj):
                                if not silent and msg_obj:
                                    bot.reply_to(msg_obj, f"{PEM['wait']} Retrying...", parse_mode='HTML')
                                time.sleep(2)
                                threading.Thread(target=run_js_script, args=(path, owner, folder, fn, msg_obj, attempt + 1, silent)).start()
                                return
                            return
                    if not silent and msg_obj:
                        bot.reply_to(msg_obj, f"{PEM['no']} Error:\n<pre>{err[:500]}</pre>", parse_mode='HTML')
                    return
            except subprocess.TimeoutExpired:
                if cp and cp.poll() is None:
                    cp.kill()
                    cp.communicate()
            except FileNotFoundError:
                if not silent and msg_obj:
                    bot.reply_to(msg_obj, f"{PEM['no']} 'node' not found.", parse_mode='HTML')
                return
            except Exception as e:
                if not silent and msg_obj:
                    bot.reply_to(msg_obj, f"{PEM['no']} Error: {e}", parse_mode='HTML')
                return
            finally:
                if cp and cp.poll() is None:
                    cp.kill()
                    cp.communicate()

        log_path = os.path.join(folder, f"{os.path.splitext(fn)[0]}.log")
        lf = None
        pr = None
        try:
            lf = open(log_path, 'w', encoding='utf-8', errors='ignore')
        except Exception as e:
            if not silent and msg_obj:
                bot.reply_to(msg_obj, f"{PEM['no']} Log: {e}", parse_mode='HTML')
            return
        try:
            si = None
            cf = 0
            if os.name == 'nt':
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = subprocess.SW_HIDE
            pr = subprocess.Popen(['node', path], cwd=folder,
                                  stdout=lf, stderr=lf, stdin=subprocess.PIPE,
                                  startupinfo=si, creationflags=cf,
                                  encoding='utf-8', errors='ignore')
            chat_id = msg_obj.chat.id if msg_obj else owner
            bot_scripts[key] = {
                'process': pr, 'log_file': lf, 'file_name': fn,
                'chat_id': chat_id, 'script_owner_id': owner,
                'start_time': datetime.now(), 'user_folder': folder,
                'type': 'js', 'script_key': key
            }
            if not silent and msg_obj:
                bot.reply_to(msg_obj, f"{PEM['ok']} JS script '{fn}' started! (PID: {pr.pid})", parse_mode='HTML')
        except FileNotFoundError:
            if lf and not lf.closed:
                lf.close()
            if not silent and msg_obj:
                bot.reply_to(msg_obj, f"{PEM['no']} 'node' not found.", parse_mode='HTML')
            bot_scripts.pop(key, None)
        except Exception as e:
            if lf and not lf.closed:
                lf.close()
            if not silent and msg_obj:
                bot.reply_to(msg_obj, f"{PEM['no']} Error: {e}", parse_mode='HTML')
            if pr and pr.poll() is None:
                kill_process_tree({'process': pr, 'log_file': lf, 'script_key': key})
            bot_scripts.pop(key, None)
    except Exception as e:
        if not silent and msg_obj:
            bot.reply_to(msg_obj, f"{PEM['no']} Error: {e}", parse_mode='HTML')
        if key in bot_scripts:
            kill_process_tree(bot_scripts[key])
            del bot_scripts[key]

# --- Background Auto-Restart Watchdog (Every 20s) ---
def auto_restart_watchdog():
    while True:
        time.sleep(20)
        try:
            for k, cfg in list(bot_settings.items()):
                if not cfg.get("auto_restart"):
                    continue
                if "_" not in k:
                    continue
                owner_s, fn = k.split("_", 1)
                try:
                    owner = int(owner_s)
                except ValueError:
                    continue
                if not is_bot_running(owner, fn):
                    folder = get_user_folder(owner)
                    fp = os.path.join(folder, fn)
                    if os.path.exists(fp):
                        ft = next((t for n, t in user_files.get(owner, []) if n == fn),
                                  'js' if fn.endswith('.js') else 'py')
                        logger.info(f"Auto-Restarting {fn} for user {owner}...")
                        if ft == 'js':
                            threading.Thread(target=run_js_script, args=(fp, owner, folder, fn, None, 1, True), daemon=True).start()
                        else:
                            threading.Thread(target=run_script, args=(fp, owner, folder, fn, None, 1, True), daemon=True).start()
        except Exception as e:
            logger.error(f"Watchdog err: {e}")

# --- File DB Ops ---
def save_user_file(uid, fn, ft='py'):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('INSERT OR REPLACE INTO user_files (user_id, file_name, file_type) VALUES (?, ?, ?)', (uid, fn, ft))
            conn.commit()
            if uid not in user_files:
                user_files[uid] = []
            user_files[uid] = [(n, t) for n, t in user_files[uid] if n != fn]
            user_files[uid].append((fn, ft))
        except Exception as e:
            logger.error(f"save_user_file: {e}")
        finally:
            conn.close()

def remove_user_file_db(uid, fn):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('DELETE FROM user_files WHERE user_id = ? AND file_name = ?', (uid, fn))
            c.execute('DELETE FROM bot_settings WHERE user_id = ? AND file_name = ?', (uid, fn))
            conn.commit()
            bot_settings.pop(f"{uid}_{fn}", None)
            if uid in user_files:
                user_files[uid] = [f for f in user_files[uid] if f[0] != fn]
                if not user_files[uid]:
                    del user_files[uid]
        except Exception as e:
            logger.error(f"remove_user_file: {e}")
        finally:
            conn.close()

def add_active_user(uid):
    touch_user_activity(uid, is_new=True)

def save_subscription(uid, exp, file_limit=SUBSCRIBED_USER_LIMIT):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('INSERT OR REPLACE INTO subscriptions (user_id, expiry) VALUES (?, ?)', (uid, exp.isoformat()))
            conn.commit()
            user_subscriptions[uid] = {'expiry': exp, 'file_limit': file_limit}
        except Exception as e:
            logger.error(f"save_sub: {e}")
        finally:
            conn.close()

def remove_subscription_db(uid):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('DELETE FROM subscriptions WHERE user_id = ?', (uid,))
            conn.commit()
            user_subscriptions.pop(uid, None)
        except Exception as e:
            logger.error(f"remove_sub: {e}")
        finally:
            conn.close()

def add_admin_db(uid):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (uid,))
            conn.commit()
            admin_ids.add(uid)
        except Exception as e:
            logger.error(f"add_admin: {e}")
        finally:
            conn.close()

def remove_admin_db(uid):
    if uid == OWNER_ID:
        return False
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        removed = False
        try:
            c.execute('DELETE FROM admins WHERE user_id = ?', (uid,))
            conn.commit()
            removed = c.rowcount > 0
            if removed:
                admin_ids.discard(uid)
            return removed
        except Exception as e:
            logger.error(f"remove_admin: {e}")
            return False
        finally:
            conn.close()

# --- Force Join Channels ---
def get_force_channels():
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        try:
            c = conn.cursor()
            c.execute('SELECT chat_id, title, invite_link FROM force_channels ORDER BY title')
            return c.fetchall()
        finally:
            conn.close()

def add_force_channel_db(chat_id, title, invite_link):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        try:
            conn.execute('INSERT OR REPLACE INTO force_channels (chat_id, title, invite_link) VALUES (?, ?, ?)',
                         (str(chat_id), title, invite_link))
            conn.commit()
        finally:
            conn.close()

def remove_force_channel_db(chat_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        try:
            cur = conn.execute('DELETE FROM force_channels WHERE chat_id = ?', (str(chat_id),))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

def user_joined_required_channels(uid):
    if not system_settings.get("force_join", True):
        return True
    if uid in admin_ids:
        return True
    for chat_id, _, _ in get_force_channels():
        try:
            member = bot.get_chat_member(chat_id, uid)
            if member.status not in ('member', 'administrator', 'creator'):
                return False
        except Exception:
            return False
    return True

def send_force_join_prompt(chat_id, uid):
    channels = get_force_channels()
    if not channels:
        return False
    kb = []
    for _, title, _ in channels:
        kb.append([rbtn(f"📢 Join {title}", "5352597830089347330", "primary")])
    kb.append([rbtn("✅ Joined - Check", "6111726981760423576", "success")])
    links = "\n".join(f"• <a href=\"{link}\">{title}</a>" for _, title, link in channels)
    raw_send(chat_id, f"{PEM['warn']} <b>Bot use করতে আগে নিচের channel/group-এ join করুন:</b>\n\n{links}\n\nJoin করার পর <b>✅ Joined - Check</b> চাপুন।", reply_keyboard=kb)
    return True

def process_add_channel(m):
    uid = m.from_user.id
    user_states.pop(uid, None)
    if uid not in admin_ids:
        return
    if m.text and m.text.lower() == '/cancel':
        raw_send(m.chat.id, "Cancelled.", reply_keyboard=get_admin_panel_kb(uid))
        return
    value = (m.text or '').strip()
    try:
        if value.startswith('https://t.me/'):
            username = '@' + value.rstrip('/').split('/')[-1]
        elif value.startswith('@'):
            username = value
        else:
            username = value
        chat = bot.get_chat(username)
        chat_id = str(chat.id)
        title = getattr(chat, 'title', None) or getattr(chat, 'username', None) or chat_id
        link = getattr(chat, 'invite_link', None)
        if not link:
            un = getattr(chat, 'username', None)
            if un:
                link = f"https://t.me/{un}"
            else:
                try:
                    link = bot.export_chat_invite_link(chat.id)
                except Exception:
                    link = None
        if not link:
            raw_send(m.chat.id, f"{PEM['no']} Invite link পাওয়া যায়নি। Bot-কে channel/group admin করে আবার try করুন.", reply_keyboard=get_admin_panel_kb(uid))
            return
        me = bot.get_me()
        bot.get_chat_member(chat.id, me.id)
        add_force_channel_db(chat_id, title, link)
        write_audit_log(uid, f"Added force channel {title} ({chat_id})")
        raw_send(m.chat.id, f"{PEM['ok']} Added: <b>{title}</b>\n<code>{chat_id}</code>", reply_keyboard=get_admin_panel_kb(uid))
    except Exception as e:
        raw_send(m.chat.id, f"{PEM['no']} Channel/group add failed. Bot-কে সেখানে admin করুন এবং @username/link দিন.\n<code>{str(e)[:500]}</code>", reply_keyboard=get_admin_panel_kb(uid))

# --- Host Request Notifications ---
def host_request_text(status, aid, ap):
    username = ap.get("username")
    uname = f"@{username}" if username else "N/A"
    created = datetime.fromtimestamp(ap.get("timestamp", time.time())).strftime("%Y-%m-%d %H:%M:%S")
    filename = ap.get("file_name", "Unknown")
    user_id = ap.get("user_id", "N/A")
    if status == "pending":
        heading = "⚡ NEW BOT HOSTING REQUEST"
        status_line = "STATUS: PENDING 🎯"
    elif status == "approved":
        heading = "🎉 NEW BOT SUCCESSFULLY HOSTED ✅"
        status_line = "STATUS: SUCCESSFUL ✅"
    else:
        heading = "🚫 NEW BOT REQUEST CANCELED ❌"
        status_line = "STATUS: CANCELED ❌"
    return (
        f"{heading}\n\n"
        f"🤖 FILE INFORMATION\n\n"
        f"NAME: {filename}\n"
        f"ORDER ID: {aid}\n"
        f"TIME: {created}\n\n"
        f"👤 CLIENT INFO\n\n"
        f"Username: {uname}\n"
        f"ID: {user_id}\n\n"
        f"{status_line}\n\n"
        f"BOT = @BHHKTEAMS"
    )

def publish_pending_host_request(aid, ap):
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ APPROVE", callback_data=f"hostapprove:{aid}"),
        types.InlineKeyboardButton("❌ CANCEL", callback_data=f"hostcancel:{aid}")
    )
    try:
        sent = bot.send_message(
            UPDATE_CHANNEL_CHAT, host_request_text("pending", aid, ap),
            reply_markup=markup, disable_web_page_preview=True
        )
        ap["channel_chat_id"] = sent.chat.id
        ap["channel_message_id"] = sent.message_id
    except Exception as e:
        logger.error(f"pending update-channel notice failed: {e}")

def update_host_request_post(aid, ap, status):
    chat_id = ap.get("channel_chat_id", UPDATE_CHANNEL_CHAT)
    message_id = ap.get("channel_message_id")
    if not message_id:
        return
    try:
        bot.edit_message_text(
            host_request_text(status, aid, ap), chat_id, message_id,
            reply_markup=None, disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"update channel status edit failed: {e}")

def notify_admin_new_file(aid, uid, uname, fname, fn, ft, is_zip=False):
    txt = (
        f"{PEM['bell']} <b>New File Upload — Approval Needed!</b>\n\n"
        f"{PEM['user']} Name: <b>{fname}</b>\n"
        f"{PEM['user']} Username: @{uname or 'N/A'}\n"
        f"{PEM['user']} User ID: <code>{uid}</code>\n\n"
        f"{PEM['file']} File: <code>{fn}</code>\n"
        f"{PEM['gear']} Type: <b>{ft.upper()}</b>"
        + (f"\n📦 (ZIP Archive)" if is_zip else "") +
        f"\n\n{PEM['pin']} Approval ID: <code>{aid}</code>\n\n"
        f"{PEM['wait']} Approve to run, or Reject to delete."
    )
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Approve", callback_data=f"adm_file_app:{aid}"),
        types.InlineKeyboardButton("❌ Reject", callback_data=f"adm_file_rej:{aid}")
    )
    for admin in set([int(ADMIN_ID)] + list(admin_ids)):
        try:
            bot.send_message(admin, txt, parse_mode='HTML', reply_markup=markup, disable_web_page_preview=True)
        except Exception as e:
            logger.error(f"notify admin {admin}: {e}")

def notify_user_approved(uid, fn, ft):
    try:
        txt = (f"{PEM['ok']} <b>File Approved & Started!</b>\n\n"
               f"{PEM['file']} File: <code>{fn}</code>\n"
               f"{PEM['gear']} Type: {ft.upper()}\n\n"
               f"{PEM['rocket']} Your file is now running!")
        raw_send(uid, txt, reply_keyboard=get_main_kb(uid))
    except Exception as e:
        logger.error(f"notify_user_approved: {e}")

def notify_user_rejected(uid, fn, reason=""):
    try:
        txt = (f"{PEM['no']} <b>File Rejected!</b>\n\n"
               f"{PEM['file']} File: <code>{fn}</code>\n\n")
        if reason:
            txt += f"{PEM['msg']} Reason: {reason}\n\n"
        txt += f"{PEM['wait']} Contact support if needed."
        raw_send(uid, txt, reply_keyboard=get_main_kb(uid))
    except Exception as e:
        logger.error(f"notify_user_rejected: {e}")

# --- File Handling ---
def handle_zip(content, zname, message):
    uid = message.from_user.id
    folder = get_user_folder(uid)
    tdir = None
    try:
        tdir = tempfile.mkdtemp(prefix=f"u_{uid}_zip_")
        zp = os.path.join(tdir, zname)
        with open(zp, 'wb') as f:
            f.write(content)
        with zipfile.ZipFile(zp, 'r') as z:
            for m in z.infolist():
                mp = os.path.abspath(os.path.join(tdir, m.filename))
                if not mp.startswith(os.path.abspath(tdir)):
                    raise zipfile.BadZipFile(f"Unsafe: {m.filename}")
            z.extractall(tdir)
        items = os.listdir(tdir)
        py_f = [f for f in items if f.endswith('.py')]
        js_f = [f for f in items if f.endswith('.js')]
        req = 'requirements.txt' if 'requirements.txt' in items else None
        pkg = 'package.json' if 'package.json' in items else None
        if req:
            rp = os.path.join(tdir, req)
            bot.reply_to(message, f"{PEM['wait']} Installing Python deps...", parse_mode='HTML')
            try:
                subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', rp],
                               capture_output=True, text=True, check=True,
                               encoding='utf-8', errors='ignore')
                bot.reply_to(message, f"{PEM['ok']} Python deps installed.", parse_mode='HTML')
            except subprocess.CalledProcessError as e:
                err = f"{PEM['no']} Failed.\n<pre>{e.stderr or e.stdout}</pre>"
                if len(err) > 4000:
                    err = err[:4000] + "\n..."
                bot.reply_to(message, err, parse_mode='HTML')
                return
        if pkg:
            bot.reply_to(message, f"{PEM['wait']} Installing Node deps...", parse_mode='HTML')
            try:
                subprocess.run(['npm', 'install'], capture_output=True, text=True,
                               check=True, cwd=tdir, encoding='utf-8', errors='ignore')
                bot.reply_to(message, f"{PEM['ok']} Node deps installed.", parse_mode='HTML')
            except FileNotFoundError:
                bot.reply_to(message, f"{PEM['no']} 'npm' not found.", parse_mode='HTML')
                return
            except subprocess.CalledProcessError as e:
                err = f"{PEM['no']} Failed.\n<pre>{e.stderr or e.stdout}</pre>"
                if len(err) > 4000:
                    err = err[:4000] + "\n..."
                bot.reply_to(message, err, parse_mode='HTML')
                return
        main_s = None
        ft = None
        for p in ['main.py', 'bot.py', 'app.py']:
            if p in py_f:
                main_s = p
                ft = 'py'
                break
        if not main_s:
            for p in ['index.js', 'main.js', 'bot.js', 'app.js']:
                if p in js_f:
                    main_s = p
                    ft = 'js'
                    break
        if not main_s:
            if py_f:
                main_s = py_f[0]
                ft = 'py'
            elif js_f:
                main_s = js_f[0]
                ft = 'js'
        if not main_s:
            bot.reply_to(message, f"{PEM['no']} No .py or .js found!", parse_mode='HTML')
            return
        for name in os.listdir(tdir):
            src = os.path.join(tdir, name)
            dst = os.path.join(folder, name)
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            elif os.path.exists(dst):
                os.remove(dst)
            shutil.move(src, dst)
        save_user_file(uid, main_s, ft)
        aid = str(uuid.uuid4())[:8].upper()
        pending_approvals[aid] = {
            'user_id': uid, 'file_name': main_s, 'file_type': ft,
            'file_path': os.path.join(folder, main_s),
            'user_folder': folder, 'message_info': message,
            'is_zip': True, 'main_script': main_s, 'timestamp': time.time(),
            'username': message.from_user.username
        }
        publish_pending_host_request(aid, pending_approvals[aid])
        txt = (f"{PEM['ok']} <b>Files extracted & deps installed!</b>\n\n"
               f"{PEM['wait']} Waiting for <b>Admin Approval</b>.\n"
               f"{PEM['pin']} Approval ID: <code>{aid}</code>\n\n"
               f"You will be notified once approved.")
        raw_send(uid, txt, reply_keyboard=get_main_kb(uid))
        notify_admin_new_file(aid, uid, message.from_user.username,
                              message.from_user.first_name, main_s, ft, is_zip=True)
    except zipfile.BadZipFile as e:
        bot.reply_to(message, f"{PEM['no']} Invalid ZIP: {e}", parse_mode='HTML')
    except Exception as e:
        logger.error(f"zip err: {e}", exc_info=True)
        bot.reply_to(message, f"{PEM['no']} Error: {e}", parse_mode='HTML')
    finally:
        if tdir and os.path.exists(tdir):
            try:
                shutil.rmtree(tdir)
            except Exception:
                pass

def handle_js(path, uid, folder, fn, message):
    try:
        save_user_file(uid, fn, 'js')
        aid = str(uuid.uuid4())[:8].upper()
        pending_approvals[aid] = {
            'user_id': uid, 'file_name': fn, 'file_type': 'js',
            'file_path': path, 'user_folder': folder,
            'message_info': message, 'is_zip': False,
            'main_script': fn, 'timestamp': time.time(),
            'username': message.from_user.username
        }
        publish_pending_host_request(aid, pending_approvals[aid])
        txt = (f"{PEM['ok']} <b>JS file received!</b>\n\n"
               f"{PEM['wait']} Waiting for <b>Admin Approval</b>.\n"
               f"{PEM['pin']} Approval ID: <code>{aid}</code>")
        raw_send(uid, txt, reply_keyboard=get_main_kb(uid))
        notify_admin_new_file(aid, uid, message.from_user.username,
                              message.from_user.first_name, fn, 'js', is_zip=False)
    except Exception as e:
        logger.error(f"js err: {e}", exc_info=True)
        bot.reply_to(message, f"{PEM['no']} Error: {e}", parse_mode='HTML')

def handle_py(path, uid, folder, fn, message):
    try:
        save_user_file(uid, fn, 'py')
        aid = str(uuid.uuid4())[:8].upper()
        pending_approvals[aid] = {
            'user_id': uid, 'file_name': fn, 'file_type': 'py',
            'file_path': path, 'user_folder': folder,
            'message_info': message, 'is_zip': False,
            'main_script': fn, 'timestamp': time.time(),
            'username': message.from_user.username
        }
        publish_pending_host_request(aid, pending_approvals[aid])
        txt = (f"{PEM['ok']} <b>Python file received!</b>\n\n"
               f"{PEM['wait']} Waiting for <b>Admin Approval</b>.\n"
               f"{PEM['pin']} Approval ID: <code>{aid}</code>")
        raw_send(uid, txt, reply_keyboard=get_main_kb(uid))
        notify_admin_new_file(aid, uid, message.from_user.username,
                              message.from_user.first_name, fn, 'py', is_zip=False)
    except Exception as e:
        logger.error(f"py err: {e}", exc_info=True)
        bot.reply_to(message, f"{PEM['no']} Error: {e}", parse_mode='HTML')

# --- User Panel Screens ---
def show_plans_screen(chat_id, uid):
    bal = get_balance(uid)
    lines = [
        f"💎 <b>Available Plans</b>",
        f"💰 Your Balance: <b>৳{bal:.2f}</b>\n"
    ]
    kb = []
    if not plans_data:
        lines.append("⚠️ বর্তমানে কোনো কাস্টম প্ল্যান তৈরি করা হয়নি।")
    else:
        for code, pl in plans_data.items():
            lines.append(
                f"▫️ <b>{pl['name']}</b> (<code>{code}</code>)\n"
                f"   ⏳ মেয়াদ: <b>{pl['days']} দিন</b> | 🤖 লিমিট: <b>{pl['file_limit']} বট</b> | 💵 মূল্য: <b>৳{pl['price']:.2f}</b>"
            )
            kb.append([rbtn(f"🛒 Buy {code} (৳{pl['price']:g})", "6111799373434197692", "success")])
    kb.append([rbtn("💰 Deposit", "6111799373434197692", "primary"),
               rbtn("🔙 Back", "6109360506319935223", "primary")])
    raw_send(chat_id, "\n".join(lines), reply_keyboard=kb)

def show_profile_screen(chat_id, uid, first_name="", username=""):
    bal = get_balance(uid)
    limit = get_user_file_limit(uid)
    curr = get_user_file_count(uid)
    lim_str = str(limit) if limit != float('inf') else "Unlimited"
    running_cnt = sum(1 for fn, _ in user_files.get(uid, []) if is_bot_running(uid, fn))

    now = datetime.now()
    plan_info = "Free User"
    if uid == OWNER_ID:
        plan_info = "👑 Owner (Unlimited)"
    elif uid in admin_ids:
        plan_info = "📊 Admin (Unlimited)"
    elif uid in user_subscriptions and user_subscriptions[uid].get('expiry') and user_subscriptions[uid]['expiry'] > now:
        exp = user_subscriptions[uid]['expiry']
        rem = exp - now
        plan_info = f"✅ Active Plan (বাকি: {rem.days}d {rem.seconds // 3600}h, Exp: {exp:%Y-%m-%d})"
    elif uid in user_trials and user_trials[uid].get("expiry") and user_trials[uid]["expiry"] > now:
        exp = user_trials[uid]["expiry"]
        rem = exp - now
        plan_info = f"🎁 Free Trial Active (বাকি: {rem.days}d {rem.seconds // 3600}h)"
    elif uid in user_trials and user_trials[uid].get("used"):
        plan_info = "🎁 Free Trial (Used / Expired)"

    uname_txt = f"@{username}" if username else "Not set"
    txt = (
        f"👤 <b>User Profile</b>\n\n"
        f"• <b>Name:</b> {first_name or 'User'}\n"
        f"• <b>User ID:</b> <code>{uid}</code>\n"
        f"• <b>Username:</b> {uname_txt}\n"
        f"• <b>Balance:</b> <b>৳{bal:.2f}</b>\n"
        f"• <b>Plan / Trial:</b> {plan_info}\n"
        f"• <b>Hosted Bots:</b> {curr} / {lim_str} (🟢 Running: <b>{running_cnt}</b>)"
    )
    raw_send(chat_id, txt, reply_keyboard=get_main_kb(uid))

def show_my_bots_screen(chat_id, uid):
    files = user_files.get(uid, [])
    if not files:
        raw_send(chat_id, "🤖 <b>My Bots</b>\n\nআপনার কোনো হোস্ট করা বট নেই।", reply_keyboard=get_main_kb(uid))
        return
    lines = ["🤖 <b>Your Hosted Bots:</b>\n"]
    kb = []
    for fn, ft in sorted(files):
        running = is_bot_running(uid, fn)
        st_icon = "🟢 Running" if running else "🔴 Stopped"
        auto_tag = " | 🔁Auto" if is_auto_restart_enabled(uid, fn) else ""
        lines.append(f"• <code>{fn}</code> — {st_icon} (<code>{ft.upper()}</code>){auto_tag}")
        kb.append([rbtn(f"🤖 Bot: {fn}", "5352597830089347330", "success" if running else "primary")])
    kb.append([rbtn("🔙 Back", "6109360506319935223", "primary")])
    raw_send(chat_id, "\n".join(lines), reply_keyboard=kb)

def show_single_bot_panel(chat_id, uid, fn):
    ft = next((t for n, t in user_files.get(uid, []) if n == fn), 'js' if fn.endswith('.js') else 'py')
    m = get_bot_live_metrics(uid, fn)
    auto_on = is_auto_restart_enabled(uid, fn)
    st_text = "🟢 Running" if m["running"] else "🔴 Stopped"
    extra = ""
    if m["running"]:
        extra = (
            f"\n• <b>PID:</b> <code>{m['pid']}</code>"
            f"\n• <b>RAM:</b> {m['ram_mb']} MB"
            f"\n• <b>CPU:</b> {m['cpu_pct']}%"
            f"\n• <b>Uptime:</b> {m['uptime']}"
        )
    txt = (
        f"🤖 <b>Bot Control Panel:</b> <code>{fn}</code>\n\n"
        f"• <b>Status:</b> {st_text}\n"
        f"• <b>Type:</b> {ft.upper()}\n"
        f"• <b>Auto-Restart:</b> {'ON' if auto_on else 'OFF'}"
        f"{extra}"
    )
    raw_send(chat_id, txt, reply_keyboard=get_single_bot_kb(uid, fn))

# --- Welcome ---
def send_welcome(chat_id, user_id, first_name, username):
    global bot_locked
    if user_id in banned_users and user_id not in admin_ids:
        raw_send(chat_id, f"{PEM['no']} আপনি বট থেকে ব্যান হয়েছেন।")
        return
    touch_user_activity(user_id, is_new=(user_id not in active_users))
    bot_locked = bool(system_settings.get("bot_locked", False))
    if bot_locked and user_id not in admin_ids:
        raw_send(chat_id, f"{PEM['warn']} Bot locked by admin.", reply_keyboard=get_main_kb(user_id))
        return
    if user_id not in admin_ids and not user_joined_required_channels(user_id):
        send_force_join_prompt(chat_id, user_id)
        return
    if user_id not in active_users or user_id not in user_last_seen:
        add_active_user(user_id)
        trial_granted = grant_trial_if_available(user_id)
        try:
            bot.send_message(OWNER_ID,
                f"🎉 New user!\n👤 {first_name}\n✳️ @{username or 'N/A'}\n🆔 <code>{user_id}</code>"
                + ("\n🎁 Trial granted!" if trial_granted else ""),
                parse_mode='HTML')
        except Exception:
            pass
    limit = get_user_file_limit(user_id)
    curr = get_user_file_count(user_id)
    lim_str = str(limit) if limit != float('inf') else "Unlimited"
    bal = get_balance(user_id)
    exp_info = ""
    if user_id == OWNER_ID:
        st = f"{PEM['crown']} Owner"
    elif user_id in admin_ids:
        st = f"{PEM['admin']} Admin"
    elif user_id in user_subscriptions:
        e = user_subscriptions[user_id].get('expiry')
        if e and e > datetime.now():
            st = f"{PEM['check']} Premium"
            dl = (e - datetime.now()).days
            exp_info = f"\n{PEM['wait']} Expires in {dl} days"
        else:
            st = f"{PEM['user']} Free (Expired)"
            remove_subscription_db(user_id)
    else:
        st = f"{PEM['user']} Free User"
    txt = (f"{PEM['hi']} <b>Welcome, {first_name}!</b>\n\n"
           f"{PEM['user']} ID: <code>{user_id}</code>\n"
           f"✳️ Username: @{username or 'Not set'}\n"
           f"💰 Balance: <b>৳{bal:.2f}</b>\n"
           f"🔰 Status: {st}{exp_info}\n"
           f"{PEM['file']} Files: {curr} / {lim_str}\n\n"
           f"{PEM['gear']} Host & run Python (`.py`) or JS (`.js`) scripts.\n"
           f"{PEM['warn']} All files need <b>Admin Approval</b> before running.\n\n"
           f"{PEM['pin']} Use buttons below.")
    raw_send(chat_id, txt, reply_keyboard=get_main_kb(user_id))

# --- Commands ---
@bot.message_handler(commands=['start', 'help'])
def cmd_start(m):
    user_states.pop(m.from_user.id, None)
    send_welcome(m.chat.id, m.from_user.id, m.from_user.first_name, m.from_user.username)

@bot.message_handler(commands=['cancel'])
def cmd_cancel(m):
    uid = m.from_user.id
    user_states.pop(uid, None)
    raw_send(m.chat.id, f"{PEM['ok']} Cancelled.", reply_keyboard=get_main_kb(uid))

@bot.message_handler(commands=['admin'])
def cmd_admin(m):
    uid = m.from_user.id
    if uid in admin_ids:
        raw_send(m.chat.id, f"{PEM['admin']} <b>Admin Panel</b>\n{PEM['pin']} Use buttons below.",
                 reply_keyboard=get_admin_panel_kb(uid))
    else:
        bot.reply_to(m, f"{PEM['no']} Not admin.", parse_mode='HTML')

# --- Approve / Reject Host Request ---
def decide_host_request(aid, action, actor_id, reply_message=None):
    if actor_id not in admin_ids:
        if reply_message:
            bot.reply_to(reply_message, f"{PEM['no']} Admin only.", parse_mode='HTML')
        return False
    ap = pending_approvals.get(aid)
    if not ap:
        if reply_message:
            bot.reply_to(reply_message, f"{PEM['no']} Request not found or already handled.", parse_mode='HTML')
        return False

    file_uid = ap['user_id']
    fn = ap['file_name']
    ft = ap['file_type']
    fp = ap['file_path']
    folder = ap['user_folder']
    om = ap.get('message_info')

    pending_approvals.pop(aid, None)
    if action == "approve":
        try:
            target = om if om else reply_message
            if ft == 'py':
                threading.Thread(target=run_script, args=(fp, file_uid, folder, fn, target)).start()
            elif ft == 'js':
                threading.Thread(target=run_js_script, args=(fp, file_uid, folder, fn, target)).start()
            notify_user_approved(file_uid, fn, ft)
            update_host_request_post(aid, ap, "approved")
            write_audit_log(actor_id, f"Approved host request {aid} ({fn}) for user {file_uid}")
            if reply_message:
                bot.reply_to(reply_message,
                    f"{PEM['ok']} <b>Approved & Started!</b>\n\n"
                    f"{PEM['user']} User: <code>{file_uid}</code>\n"
                    f"{PEM['file']} File: <code>{fn}</code>",
                    parse_mode='HTML')
            return True
        except Exception as e:
            logger.error(f"approve err: {e}", exc_info=True)
            if reply_message:
                bot.reply_to(reply_message, f"{PEM['no']} Error: {e}", parse_mode='HTML')
            return False

    try:
        if os.path.exists(fp):
            os.remove(fp)
        remove_user_file_db(file_uid, fn)
    except Exception as e:
        logger.error(f"reject del: {e}")
    notify_user_rejected(file_uid, fn, reason="Admin canceled the hosting request.")
    update_host_request_post(aid, ap, "canceled")
    write_audit_log(actor_id, f"Rejected host request {aid} ({fn}) for user {file_uid}")
    if reply_message:
        bot.reply_to(reply_message,
            f"{PEM['no']} <b>Canceled & Deleted!</b>\n\n"
            f"{PEM['user']} User: <code>{file_uid}</code>\n"
            f"{PEM['file']} File: <code>{fn}</code>",
            parse_mode='HTML')
    return True

@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith(("hostapprove:", "hostcancel:", "adm_file_app:", "adm_file_rej:")))
def handle_host_request_callback(call):
    uid = call.from_user.id
    if uid not in admin_ids:
        bot.answer_callback_query(call.id, "Only admins can do this.", show_alert=True)
        return
    prefix, aid = call.data.split(":", 1)
    aid = aid.upper()
    ap = pending_approvals.get(aid)
    action = "approve" if prefix in ("hostapprove", "adm_file_app") else "cancel"
    ok = decide_host_request(aid, action, uid)
    if prefix in ("adm_file_app", "adm_file_rej"):
        try:
            label = "✅ File Approved & Started!" if ok and action == "approve" else ("❌ File Rejected & Deleted!" if ok else "⚠️ Already processed or not found.")
            bot.edit_message_text(
                f"{label}\n• Approval ID: <code>{aid}</code>\n• By Admin: <code>{uid}</code>",
                call.message.chat.id, call.message.message_id, parse_mode='HTML'
            )
        except Exception:
            pass
    try:
        bot.answer_callback_query(call.id, "Request updated!" if ok else "Already handled or unavailable.")
    except Exception:
        pass

# --- Deposit Approval Inline Callbacks ---
@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith(("dep_app:", "dep_rej:")))
def handle_deposit_callback(call):
    uid = call.from_user.id
    if uid not in admin_ids:
        bot.answer_callback_query(call.id, "Only admins can do this.", show_alert=True)
        return
    action, dep_id = call.data.split(":", 1)
    dep = pending_deposits.get(dep_id)
    if not dep:
        bot.answer_callback_query(call.id, "Deposit already processed or not found.", show_alert=True)
        return
    target_uid = dep["user_id"]
    amt = float(dep["amount"])
    if action == "dep_app":
        new_bal = add_balance_db(target_uid, amt)
        update_deposit_status_db(dep_id, "approved")
        write_audit_log(uid, f"Approved deposit {dep_id} (৳{amt:.2f}) for user {target_uid}")
        raw_send(target_uid,
                 f"✅ <b>Deposit Approved!</b>\n\n"
                 f"• Deposit ID: <code>{dep_id}</code>\n"
                 f"• Amount Added: <b>৳{amt:.2f}</b>\n"
                 f"• New Balance: <b>৳{new_bal:.2f}</b>",
                 reply_keyboard=get_main_kb(target_uid))
        try:
            bot.edit_message_text(f"✅ Approved Deposit <code>{dep_id}</code> (৳{amt:.2f}) for <code>{target_uid}</code>",
                                  call.message.chat.id, call.message.message_id, parse_mode='HTML')
        except Exception:
            pass
        bot.answer_callback_query(call.id, "Deposit approved!")
    else:
        update_deposit_status_db(dep_id, "rejected")
        write_audit_log(uid, f"Rejected deposit {dep_id} (৳{amt:.2f}) for user {target_uid}")
        raw_send(target_uid,
                 f"❌ <b>Deposit Rejected!</b>\n\n"
                 f"• Deposit ID: <code>{dep_id}</code>\n"
                 f"• Amount: <b>৳{amt:.2f}</b>\n"
                 f"• TrxID: <code>{dep['trx_id']}</code>",
                 reply_keyboard=get_main_kb(target_uid))
        try:
            bot.edit_message_text(f"❌ Rejected Deposit <code>{dep_id}</code> (৳{amt:.2f}) for <code>{target_uid}</code>",
                                  call.message.chat.id, call.message.message_id, parse_mode='HTML')
        except Exception:
            pass
        bot.answer_callback_query(call.id, "Deposit rejected.")

# --- Backup Restore Handler (ZIP / JSON) ---
def restore_from_backup_zip(zip_bytes, actor_id, chat_id):
    tdir = tempfile.mkdtemp(prefix="restore_zip_")
    try:
        zp = os.path.join(tdir, "backup.zip")
        with open(zp, "wb") as f:
            f.write(zip_bytes)
        with zipfile.ZipFile(zp, "r") as z:
            z.extractall(tdir)
        db_src = os.path.join(tdir, "bot_data.db")
        if os.path.exists(db_src):
            with DB_LOCK:
                shutil.copy2(db_src, DATABASE_PATH)
        bots_src = os.path.join(tdir, "upload_bots")
        if os.path.isdir(bots_src):
            for name in os.listdir(bots_src):
                src_p = os.path.join(bots_src, name)
                dst_p = os.path.join(UPLOAD_BOTS_DIR, name)
                if os.path.isdir(src_p):
                    if os.path.exists(dst_p):
                        shutil.rmtree(dst_p)
                    shutil.copytree(src_p, dst_p)
        aud_src = os.path.join(tdir, "audit.log")
        if os.path.exists(aud_src):
            shutil.copy2(aud_src, AUDIT_LOG_PATH)
        init_db()
        load_data()
        write_audit_log(actor_id, "Restored full system backup from ZIP")
        raw_send(chat_id, "✅ <b>Backup ZIP restored successfully!</b>", reply_keyboard=get_admin_panel_kb(actor_id))
    except Exception as e:
        raw_send(chat_id, f"❌ Restore failed: <code>{str(e)[:400]}</code>", reply_keyboard=get_admin_panel_kb(actor_id))
    finally:
        shutil.rmtree(tdir, ignore_errors=True)

def restore_from_backup_json(raw_json_str, actor_id, chat_id):
    try:
        data = json.loads(raw_json_str)
        if not isinstance(data, dict):
            raise ValueError("JSON root must be an object")
        for uid_s, bal in data.get("balances", {}).items():
            set_balance_db(int(uid_s), float(bal))
        for code, pl in data.get("plans", {}).items():
            save_plan_db(code, pl["name"], pl["file_limit"], pl["days"], pl["price"])
        for uid_s, sub in data.get("subscriptions", {}).items():
            exp_dt = datetime.fromisoformat(sub["expiry"])
            save_subscription(int(uid_s), exp_dt, sub.get("file_limit", SUBSCRIBED_USER_LIMIT))
        load_data()
        write_audit_log(actor_id, "Restored state from JSON backup")
        raw_send(chat_id, "✅ <b>JSON Backup restored successfully!</b>", reply_keyboard=get_admin_panel_kb(actor_id))
    except Exception as e:
        raw_send(chat_id, f"❌ JSON restore error: <code>{str(e)[:400]}</code>", reply_keyboard=get_admin_panel_kb(actor_id))

# --- Multi-Step State Machine ---
def handle_user_state(m):
    uid = m.from_user.id
    st = user_states.get(uid)
    if not st:
        return False
    mode = st.get("mode")
    txt = (m.text or "").strip()

    if txt.lower() == "/cancel" or txt == "🔙 Back":
        user_states.pop(uid, None)
        kb = get_admin_panel_kb(uid) if uid in admin_ids else get_main_kb(uid)
        raw_send(m.chat.id, f"{PEM['ok']} Cancelled.", reply_keyboard=kb)
        return True

    if mode == "await_deposit_amount":
        try:
            amt = float(txt)
            min_dep = float(system_settings.get("min_deposit", 20.0))
            if amt < min_dep:
                raw_send(m.chat.id, f"⚠️ সর্বনিম্ন ডিপোজিট অ্যামাউন্ট <b>৳{min_dep:.2f}</b>। আবার লিখুন বা /cancel করুন।")
                return True
            methods_kb = []
            row = []
            for m_name, flag in [("BKASH", "bkash_enabled"), ("NAGAD", "nagad_enabled"), ("ROCKET", "rocket_enabled")]:
                if system_settings.get(flag):
                    row.append(rbtn(f"💳 Pay {m_name}", "6111799373434197692", "success"))
                    if len(row) == 2:
                        methods_kb.append(row)
                        row = []
            if row:
                methods_kb.append(row)
            if not methods_kb:
                user_states.pop(uid, None)
                raw_send(m.chat.id, "❌ বর্তমানে কোনো পেমেন্ট মেথড চালু নেই।", reply_keyboard=get_main_kb(uid))
                return True
            methods_kb.append([rbtn("🔙 Back", "6109360506319935223", "primary")])
            user_states[uid] = {"mode": "await_deposit_method", "amount": amt}
            raw_send(m.chat.id,
                     f"💰 ডিপোজিট অ্যামাউন্ট: <b>৳{amt:.2f}</b>\nনিচের পেমেন্ট মেথড বেছে নিন:",
                     reply_keyboard=methods_kb)
        except ValueError:
            raw_send(m.chat.id, "⚠️ সঠিক সংখ্যায় অ্যামাউন্ট লিখুন (যেমন: <code>50</code>)।")
        return True

    if mode == "await_trx_id":
        if len(txt) < 4:
            raw_send(m.chat.id, "⚠️ সঠিক Transaction ID (TrxID) লিখুন।")
            return True
        method = st["method"]
        amt = st["amount"]
        dep_id = "DEP" + str(uuid.uuid4())[:6].upper()
        dep = {
            "deposit_id": dep_id,
            "user_id": uid,
            "username": m.from_user.username or "N/A",
            "method": method,
            "amount": amt,
            "trx_id": txt,
            "status": "pending",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_deposit_db(dep)
        user_states.pop(uid, None)
        raw_send(m.chat.id,
                 f"✅ <b>Deposit Request Submitted!</b>\n\n"
                 f"• Deposit ID: <code>{dep_id}</code>\n"
                 f"• Method: <b>{method}</b>\n"
                 f"• Amount: <b>৳{amt:.2f}</b>\n"
                 f"• TrxID: <code>{txt}</code>\n"
                 f"• Status: ⏳ Pending Approval",
                 reply_keyboard=get_main_kb(uid))

        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("✅ Approve", callback_data=f"dep_app:{dep_id}"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"dep_rej:{dep_id}")
        )
        adm_txt = (
            f"💳 <b>New Deposit Request</b>\n\n"
            f"• ID: <code>{dep_id}</code>\n"
            f"• User: @{m.from_user.username or 'N/A'} (<code>{uid}</code>)\n"
            f"• Method: <b>{method}</b>\n"
            f"• Amount: <b>৳{amt:.2f}</b>\n"
            f"• TrxID: <code>{txt}</code>\n"
            f"• Time: {dep['created_at']}"
        )
        for adm in set([int(ADMIN_ID)] + list(admin_ids)):
            try:
                bot.send_message(adm, adm_txt, parse_mode='HTML', reply_markup=markup)
            except Exception:
                pass
        return True

    if mode == "plan_make_name":
        if not txt:
            raw_send(m.chat.id, "⚠️ প্ল্যানের নাম দিন।")
            return True
        user_states[uid] = {"mode": "plan_make_limit", "name": txt}
        raw_send(m.chat.id, "🤖 এই প্ল্যানে কয়টি বট চালানো যাবে (file_limit) সংখ্যা লিখুন:")
        return True

    if mode == "plan_make_limit":
        try:
            fl = int(txt)
            if fl <= 0:
                raise ValueError()
            user_states[uid] = {"mode": "plan_make_days", "name": st["name"], "file_limit": fl}
            raw_send(m.chat.id, "⏳ প্ল্যানের মেয়াদ কত দিন (days) সংখ্যা লিখুন:")
        except ValueError:
            raw_send(m.chat.id, "⚠️ সঠিক সংখ্যা লিখুন (যেমন: 3)।")
        return True

    if mode == "plan_make_days":
        try:
            days = int(txt)
            if days <= 0:
                raise ValueError()
            user_states[uid] = {
                "mode": "plan_make_price",
                "name": st["name"],
                "file_limit": st["file_limit"],
                "days": days
            }
            raw_send(m.chat.id, "💵 প্ল্যানের দাম কত টাকা (৳) লিখুন:")
        except ValueError:
            raw_send(m.chat.id, "⚠️ সঠিক দিন সংখ্যা লিখুন (যেমন: 30)।")
        return True

    if mode == "plan_make_price":
        try:
            price = float(txt)
            if price < 0:
                raise ValueError()
            code = "PLAN" + str(uuid.uuid4())[:4].upper()
            save_plan_db(code, st["name"], st["file_limit"], st["days"], price)
            user_states.pop(uid, None)
            write_audit_log(uid, f"Created plan {code} ({st['name']}) - {st['days']}d, {st['file_limit']} bots, ৳{price:.2f}")
            raw_send(m.chat.id,
                     f"✅ <b>New Plan Created!</b>\n\n"
                     f"• Code: <code>{code}</code>\n"
                     f"• Name: <b>{st['name']}</b>\n"
                     f"• Bot Limit: <b>{st['file_limit']}</b>\n"
                     f"• Validity: <b>{st['days']} days</b>\n"
                     f"• Price: <b>৳{price:.2f}</b>",
                     reply_keyboard=get_admin_panel_kb(uid))
        except ValueError:
            raw_send(m.chat.id, "⚠️ সঠিক মূল্য লিখুন (যেমন: 100)।")
        return True

    if mode in ("set_bkash_no", "set_nagad_no", "set_rocket_no"):
        key_map = {
            "set_bkash_no": ("bkash_number", "bkash_enabled", "bKash"),
            "set_nagad_no": ("nagad_number", "nagad_enabled", "Nagad"),
            "set_rocket_no": ("rocket_number", "rocket_enabled", "Rocket"),
        }
        num_key, en_key, label = key_map[mode]
        save_system_setting_db(num_key, txt)
        next_step = st.get("next_enable")
        user_states.pop(uid, None)
        if next_step:
            save_system_setting_db(en_key, True)
            write_audit_log(uid, f"Set {label} number to {txt} and enabled {label}")
            raw_send(m.chat.id, f"✅ {label} নম্বর সেট হয়েছে (<code>{txt}</code>) এবং <b>{label}: ON</b> করা হয়েছে।",
                     reply_keyboard=get_payment_setup_kb())
        else:
            write_audit_log(uid, f"Set {label} number to {txt}")
            raw_send(m.chat.id, f"✅ {label} নম্বর আপডেট হয়েছে: <code>{txt}</code>",
                     reply_keyboard=get_payment_setup_kb())
        return True

    if mode == "set_min_deposit":
        try:
            val = float(txt)
            if val <= 0:
                raise ValueError()
            save_system_setting_db("min_deposit", val)
            user_states.pop(uid, None)
            write_audit_log(uid, f"Set min deposit to ৳{val:.2f}")
            raw_send(m.chat.id, f"✅ সর্বনিম্ন ডিপোজিট সীমা সেট হয়েছে: <b>৳{val:.2f}</b>",
                     reply_keyboard=get_payment_setup_kb())
        except ValueError:
            raw_send(m.chat.id, "⚠️ সঠিক অ্যামাউন্ট লিখুন (যেমন: 20)।")
        return True

    if mode == "set_trial_days":
        try:
            td = int(txt)
            if td < 0:
                raise ValueError()
            save_system_setting_db("trial_days", td)
            user_states.pop(uid, None)
            write_audit_log(uid, f"Set trial days to {td}")
            raw_send(m.chat.id, f"✅ Free Trial মেয়াদ সেট হয়েছে: <b>{td} দিন</b>",
                     reply_keyboard=get_system_toggles_kb())
        except ValueError:
            raw_send(m.chat.id, "⚠️ ০ বা তার বেশি পূর্ণসংখ্যা লিখুন (যেমন: 3)।")
        return True

    if mode == "await_json_backup":
        user_states.pop(uid, None)
        restore_from_backup_json(txt, uid, m.chat.id)
        return True

    # --- Others Option Stateful Inputs ---
    if mode == "others_ban_user":
        user_states.pop(uid, None)
        try:
            tid = int(txt)
            if ban_user_db(tid):
                write_audit_log(uid, f"Banned user {tid}")
                raw_send(m.chat.id, f"🚫 User <code>{tid}</code> banned!", reply_keyboard=get_others_options_kb())
            else:
                raw_send(m.chat.id, "⚠️ Owner-কে ব্যান করা যাবে না।", reply_keyboard=get_others_options_kb())
        except ValueError:
            raw_send(m.chat.id, "⚠️ সঠিক User ID লিখুন।", reply_keyboard=get_others_options_kb())
        return True

    if mode == "others_unban_user":
        user_states.pop(uid, None)
        try:
            tid = int(txt)
            if unban_user_db(tid):
                write_audit_log(uid, f"Unbanned user {tid}")
                raw_send(m.chat.id, f"🔓 User <code>{tid}</code> unbanned!", reply_keyboard=get_others_options_kb())
            else:
                raw_send(m.chat.id, "⚠️ User banned তালিকায় নেই।", reply_keyboard=get_others_options_kb())
        except ValueError:
            raw_send(m.chat.id, "⚠️ সঠিক User ID লিখুন।", reply_keyboard=get_others_options_kb())
        return True

    if mode in ("others_add_bal", "others_deduct_bal"):
        user_states.pop(uid, None)
        parts = txt.split()
        if len(parts) != 2:
            raw_send(m.chat.id, "⚠️ ফরম্যাট: <code>USER_ID AMOUNT</code> (যেমন: <code>8225743320 50</code>)", reply_keyboard=get_others_options_kb())
            return True
        try:
            tid = int(parts[0])
            amt = float(parts[1])
            if amt <= 0:
                raise ValueError()
            if mode == "others_add_bal":
                nb = add_balance_db(tid, amt)
                write_audit_log(uid, f"Added ৳{amt:.2f} to {tid}")
                raw_send(m.chat.id, f"✅ Added <b>৳{amt:.2f}</b> to <code>{tid}</code>. New Balance: <b>৳{nb:.2f}</b>", reply_keyboard=get_others_options_kb())
            else:
                nb = add_balance_db(tid, -amt)
                write_audit_log(uid, f"Deducted ৳{amt:.2f} from {tid}")
                raw_send(m.chat.id, f"✅ Deducted <b>৳{amt:.2f}</b> from <code>{tid}</code>. New Balance: <b>৳{nb:.2f}</b>", reply_keyboard=get_others_options_kb())
        except ValueError:
            raw_send(m.chat.id, "⚠️ সঠিক ID এবং অ্যামাউন্ট লিখুন।", reply_keyboard=get_others_options_kb())
        return True

    if mode == "others_user_lookup":
        user_states.pop(uid, None)
        try:
            tid = int(txt)
            fls = user_files.get(tid, [])
            run_c = sum(1 for fn, _ in fls if is_bot_running(tid, fn))
            sub_exp = user_subscriptions.get(tid, {}).get("expiry")
            sub_s = sub_exp.strftime("%Y-%m-%d") if sub_exp else "None"
            info = (
                f"🔎 <b>User Lookup:</b> <code>{tid}</code>\n\n"
                f"• Balance: <b>৳{get_balance(tid):.2f}</b>\n"
                f"• Subscription Exp: <b>{sub_s}</b>\n"
                f"• Hosted Files: <b>{len(fls)}</b> (Running: <b>{run_c}</b>)\n"
                f"• Banned: <b>{'Yes' if tid in banned_users else 'No'}</b>\n"
                f"• Last Seen: <code>{user_last_seen.get(tid, 'N/A')}</code>"
            )
            raw_send(m.chat.id, info, reply_keyboard=get_others_options_kb())
        except ValueError:
            raw_send(m.chat.id, "⚠️ সঠিক User ID লিখুন।", reply_keyboard=get_others_options_kb())
        return True

    if mode == "others_del_plan":
        user_states.pop(uid, None)
        code = txt.upper()
        if delete_plan_db(code):
            write_audit_log(uid, f"Deleted plan {code}")
            raw_send(m.chat.id, f"🗑️ Plan <code>{code}</code> deleted!", reply_keyboard=get_others_options_kb())
        else:
            raw_send(m.chat.id, f"⚠️ Plan <code>{code}</code> পাওয়া যায়নি।", reply_keyboard=get_others_options_kb())
        return True

    if mode == "others_search_file":
        user_states.pop(uid, None)
        q = txt.lower()
        matches = []
        for o_id, fls in user_files.items():
            for fn, ft in fls:
                if q in fn.lower():
                    matches.append(f"• U:<code>{o_id}</code> | <code>{fn}</code> ({ft}) | {'🟢' if is_bot_running(o_id, fn) else '🔴'}")
        if not matches:
            raw_send(m.chat.id, f"🔍 '{txt}' দিয়ে কোনো ফাইল পাওয়া যায়নি।", reply_keyboard=get_others_options_kb())
        else:
            raw_send(m.chat.id, f"🔍 <b>Search Results ({len(matches)}):</b>\n\n" + "\n".join(matches[:30]), reply_keyboard=get_others_options_kb())
        return True

    return False

# --- Others Option Action Executor (30 Options) ---
def execute_others_option(opt_name, m):
    uid = m.from_user.id
    chat_id = m.chat.id

    if opt_name == "💻 Server Stats":
        up_sec = int((datetime.now() - BOT_START_TIME).total_seconds())
        d, rem = divmod(up_sec, 86400)
        h, rem = divmod(rem, 3600)
        mn, sc = divmod(rem, 60)
        raw_send(chat_id,
                 f"💻 <b>Server Stats</b>\n\n"
                 f"• OS: <code>{os.name}</code> / Python <code>{sys.version.split()[0]}</code>\n"
                 f"• Bot Uptime: <b>{d}d {h}h {mn}m {sc}s</b>\n"
                 f"• Active Users: <b>{len(active_users)}</b>",
                 reply_keyboard=get_others_options_kb())

    elif opt_name == "🧠 RAM & CPU":
        vm = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.2)
        proc_ram = round(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024), 2)
        raw_send(chat_id,
                 f"🧠 <b>RAM & CPU</b>\n\n"
                 f"• System RAM: <b>{vm.percent}%</b> ({round(vm.used / (1024**3), 2)} / {round(vm.total / (1024**3), 2)} GB)\n"
                 f"• CPU Usage: <b>{cpu}%</b>\n"
                 f"• Bot Process RAM: <b>{proc_ram} MB</b>",
                 reply_keyboard=get_others_options_kb())

    elif opt_name == "💾 Disk Usage":
        du = psutil.disk_usage(BASE_DIR)
        raw_send(chat_id,
                 f"💾 <b>Disk Usage</b>\n\n"
                 f"• Total: <b>{round(du.total / (1024**3), 2)} GB</b>\n"
                 f"• Used: <b>{round(du.used / (1024**3), 2)} GB</b> ({du.percent}%)\n"
                 f"• Free: <b>{round(du.free / (1024**3), 2)} GB</b>",
                 reply_keyboard=get_others_options_kb())

    elif opt_name == "🔄 Reboot Bot":
        write_audit_log(uid, "Triggered bot reboot via Others Option")
        raw_send(chat_id, "🔄 <b>Bot Rebooting...</b>")
        time.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    elif opt_name == "🛑 Stop All Bots":
        cnt = 0
        for k in list(bot_scripts.keys()):
            if k in bot_scripts:
                kill_process_tree(bot_scripts[k])
                bot_scripts.pop(k, None)
                cnt += 1
        write_audit_log(uid, f"Stopped all {cnt} running bots")
        raw_send(chat_id, f"🛑 Stopped <b>{cnt}</b> running bots.", reply_keyboard=get_others_options_kb())

    elif opt_name == "🔁 Restart All Bots":
        for k in list(bot_scripts.keys()):
            if k in bot_scripts:
                kill_process_tree(bot_scripts[k])
                bot_scripts.pop(k, None)
        run_all_scripts(m)

    elif opt_name == "🧹 Clear Temp/Logs":
        removed = 0
        for root_d, _, fnames in os.walk(UPLOAD_BOTS_DIR):
            for fn_i in fnames:
                if fn_i.endswith(".log"):
                    try:
                        os.remove(os.path.join(root_d, fn_i))
                        removed += 1
                    except Exception:
                        pass
        for item in os.listdir(tempfile.gettempdir()):
            if item.startswith(("u_", "restore_zip_")):
                p = os.path.join(tempfile.gettempdir(), item)
                try:
                    if os.path.isdir(p):
                        shutil.rmtree(p, ignore_errors=True)
                    else:
                        os.remove(p)
                    removed += 1
                except Exception:
                    pass
        write_audit_log(uid, f"Cleared {removed} temp/log items")
        raw_send(chat_id, f"🧹 Cleared <b>{removed}</b> log/temp items.", reply_keyboard=get_others_options_kb())

    elif opt_name == "📋 Active Processes":
        lines = []
        for k, info in list(bot_scripts.items()):
            owner_s, fn = k.split("_", 1)
            if is_bot_running(int(owner_s), fn):
                met = get_bot_live_metrics(int(owner_s), fn)
                lines.append(f"• PID <code>{met['pid']}</code> | U:<code>{owner_s}</code> | <code>{fn}</code> | {met['ram_mb']}MB | {met['uptime']}")
        raw_send(chat_id,
                 f"📋 <b>Active Hosted Processes ({len(lines)}):</b>\n\n" + ("\n".join(lines[:25]) if lines else "None running."),
                 reply_keyboard=get_others_options_kb())

    elif opt_name == "📦 Export DB JSON":
        payload = {
            "balances": {str(k): v for k, v in user_balances.items()},
            "plans": plans_data,
            "subscriptions": {
                str(k): {"expiry": v["expiry"].isoformat(), "file_limit": v.get("file_limit", SUBSCRIBED_USER_LIMIT)}
                for k, v in user_subscriptions.items() if v.get("expiry")
            }
        }
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
        json.dump(payload, tmp, indent=2, ensure_ascii=False)
        tmp.close()
        try:
            with open(tmp.name, "rb") as f:
                bot.send_document(chat_id, f, visible_file_name=f"db_export_{datetime.now():%Y%m%d_%H%M%S}.json")
        finally:
            try:
                os.remove(tmp.name)
            except Exception:
                pass

    elif opt_name == "🩺 Health Check":
        db_ok = os.path.exists(DATABASE_PATH)
        raw_send(chat_id,
                 f"🩺 <b>Health Check</b>\n\n"
                 f"• Database: {'✅ OK' if db_ok else '❌ Missing'}\n"
                 f"• Upload Dir: {'✅ OK' if os.path.isdir(UPLOAD_BOTS_DIR) else '❌ Missing'}\n"
                 f"• Pending File Approvals: <b>{len(pending_approvals)}</b>\n"
                 f"• Pending Deposits: <b>{len(pending_deposits)}</b>",
                 reply_keyboard=get_others_options_kb())

    elif opt_name == "👥 Total Users":
        raw_send(chat_id, f"👥 <b>Total Registered Users:</b> <b>{len(active_users)}</b>", reply_keyboard=get_others_options_kb())

    elif opt_name == "🟢 Active Today":
        today_s = datetime.now().strftime("%Y-%m-%d")
        cnt = sum(1 for _, ls in user_last_seen.items() if str(ls).startswith(today_s))
        raw_send(chat_id, f"🟢 <b>Active Today ({today_s}):</b> <b>{cnt}</b> users", reply_keyboard=get_others_options_kb())

    elif opt_name == "🆕 New Users (7d)":
        cutoff = datetime.now() - timedelta(days=7)
        cnt = 0
        with DB_LOCK:
            conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
            for (ja,) in conn.execute("SELECT joined_at FROM active_users").fetchall():
                if ja:
                    try:
                        if datetime.fromisoformat(ja) >= cutoff:
                            cnt += 1
                    except Exception:
                        pass
            conn.close()
        raw_send(chat_id, f"🆕 <b>New Users (Last 7 Days):</b> <b>{cnt}</b>", reply_keyboard=get_others_options_kb())

    elif opt_name == "🚫 Ban User":
        user_states[uid] = {"mode": "others_ban_user"}
        raw_send(chat_id, "🚫 যে ইউজারকে ব্যান করতে চান তার <b>User ID</b> লিখুন:", reply_keyboard=[[rbtn("🔙 Back", "6109360506319935223", "primary")]])

    elif opt_name == "🔓 Unban User":
        user_states[uid] = {"mode": "others_unban_user"}
        raw_send(chat_id, "🔓 যে ইউজারকে আনব্যান করতে চান তার <b>User ID</b> লিখুন:", reply_keyboard=[[rbtn("🔙 Back", "6109360506319935223", "primary")]])

    elif opt_name == "📋 Banned List":
        b_txt = "\n".join(f"• <code>{b}</code>" for b in sorted(banned_users)) or "No banned users."
        raw_send(chat_id, f"📋 <b>Banned Users ({len(banned_users)}):</b>\n\n{b_txt}", reply_keyboard=get_others_options_kb())

    elif opt_name == "💎 VIP Users List":
        now = datetime.now()
        vips = [f"• <code>{u}</code> (Exp: {d['expiry']:%Y-%m-%d})" for u, d in user_subscriptions.items() if d.get("expiry") and d["expiry"] > now]
        raw_send(chat_id, f"💎 <b>Active VIP / Subscribed Users ({len(vips)}):</b>\n\n" + ("\n".join(vips[:30]) if vips else "None."), reply_keyboard=get_others_options_kb())

    elif opt_name == "💰 Add Balance":
        user_states[uid] = {"mode": "others_add_bal"}
        raw_send(chat_id, "💰 লিখুন: <code>USER_ID AMOUNT</code> (যেমন: <code>8225743320 50</code>)", reply_keyboard=[[rbtn("🔙 Back", "6109360506319935223", "primary")]])

    elif opt_name == "💸 Deduct Balance":
        user_states[uid] = {"mode": "others_deduct_bal"}
        raw_send(chat_id, "💸 লিখুন: <code>USER_ID AMOUNT</code> (যেমন: <code>8225743320 20</code>)", reply_keyboard=[[rbtn("🔙 Back", "6109360506319935223", "primary")]])

    elif opt_name == "🔎 User Lookup":
        user_states[uid] = {"mode": "others_user_lookup"}
        raw_send(chat_id, "🔎 তথ্য দেখতে ইউজারের <b>User ID</b> লিখুন:", reply_keyboard=[[rbtn("🔙 Back", "6109360506319935223", "primary")]])

    elif opt_name == "📋 All Plans List":
        if not plans_data:
            raw_send(chat_id, "📋 কোনো প্ল্যান নেই।", reply_keyboard=get_others_options_kb())
        else:
            lines = [f"• <code>{c}</code> | <b>{p['name']}</b> | {p['days']}d | Lim:{p['file_limit']} | <b>৳{p['price']:.2f}</b>" for c, p in plans_data.items()]
            raw_send(chat_id, "📋 <b>All Plans:</b>\n\n" + "\n".join(lines), reply_keyboard=get_others_options_kb())

    elif opt_name == "🗑️ Delete Plan":
        user_states[uid] = {"mode": "others_del_plan"}
        raw_send(chat_id, "🗑️ যে প্ল্যান ডিলিট করতে চান তার <b>Plan Code</b> লিখুন (যেমন: <code>PLAN12AB</code>):", reply_keyboard=[[rbtn("🔙 Back", "6109360506319935223", "primary")]])

    elif opt_name == "📁 All Hosted Files":
        lines = []
        for o_id, fls in user_files.items():
            for fn, ft in fls:
                lines.append(f"• U:<code>{o_id}</code> | <code>{fn}</code> ({ft}) | {'🟢' if is_bot_running(o_id, fn) else '🔴'}")
        raw_send(chat_id, f"📁 <b>All Hosted Files ({len(lines)}):</b>\n\n" + ("\n".join(lines[:30]) if lines else "No files."), reply_keyboard=get_others_options_kb())

    elif opt_name == "🔍 Search File":
        user_states[uid] = {"mode": "others_search_file"}
        raw_send(chat_id, "🔍 ফাইলের নাম বা অংশ লিখুন:", reply_keyboard=[[rbtn("🔙 Back", "6109360506319935223", "primary")]])

    elif opt_name == "📦 Zip All User Files":
        if not os.path.isdir(UPLOAD_BOTS_DIR) or not os.listdir(UPLOAD_BOTS_DIR):
            raw_send(chat_id, "📦 কোনো হোস্ট করা ফাইল নেই।", reply_keyboard=get_others_options_kb())
            return
        tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        tmp.close()
        try:
            with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
                for root_d, _, fnames in os.walk(UPLOAD_BOTS_DIR):
                    for fn_i in fnames:
                        fp = os.path.join(root_d, fn_i)
                        zf.write(fp, arcname=os.path.relpath(fp, UPLOAD_BOTS_DIR))
            with open(tmp.name, "rb") as f:
                bot.send_document(chat_id, f, visible_file_name=f"all_user_bots_{datetime.now():%Y%m%d_%H%M%S}.zip")
        finally:
            try:
                os.remove(tmp.name)
            except Exception:
                pass

    elif opt_name == "⚠️ Error Logs Scan":
        hits = []
        for root_d, _, fnames in os.walk(UPLOAD_BOTS_DIR):
            for fn_i in fnames:
                if fn_i.endswith(".log"):
                    lp = os.path.join(root_d, fn_i)
                    try:
                        with open(lp, "r", encoding="utf-8", errors="ignore") as f:
                            txt_l = f.read()
                        if any(k in txt_l.lower() for k in ("error", "traceback", "exception")):
                            hits.append(f"• <code>{fn_i}</code> ({os.path.basename(root_d)})")
                    except Exception:
                        pass
        raw_send(chat_id, f"⚠️ <b>Error Logs Scan ({len(hits)}):</b>\n\n" + ("\n".join(hits[:25]) if hits else "No error logs found."), reply_keyboard=get_others_options_kb())

    elif opt_name == "📊 Hosting Summary":
        tot_f = sum(len(v) for v in user_files.values())
        run_f = sum(1 for o_id, fls in user_files.items() for fn, _ in fls if is_bot_running(o_id, fn))
        raw_send(chat_id,
                 f"📊 <b>Hosting Summary</b>\n\n"
                 f"• Users with Bots: <b>{len(user_files)}</b>\n"
                 f"• Total Files: <b>{tot_f}</b>\n"
                 f"• Currently Running: <b>{run_f}</b>\n"
                 f"• Stopped Files: <b>{max(0, tot_f - run_f)}</b>",
                 reply_keyboard=get_others_options_kb())

    elif opt_name == "🔔 Test Admin Alert":
        raw_send(uid, f"🔔 <b>Test Admin Alert</b> — সব ঠিকঠাক কাজ করছে! ({datetime.now():%H:%M:%S})", reply_keyboard=get_others_options_kb())

    elif opt_name == "🧾 System Info":
        raw_send(chat_id,
                 f"🧾 <b>System Info</b>\n\n"
                 f"• Owner ID: <code>{OWNER_ID}</code>\n"
                 f"• Total Admins: <b>{len(admin_ids)}</b>\n"
                 f"• Total Plans: <b>{len(plans_data)}</b>\n"
                 f"• Force Channels: <b>{len(get_force_channels())}</b>",
                 reply_keyboard=get_others_options_kb())

    elif opt_name == "📌 Quick Help":
        raw_send(chat_id,
                 "📌 <b>Quick Admin Help</b>\n\n"
                 "• নতুন ফাইল আপলোডে ইনলাইন <b>✅ Approve</b> / <b>❌ Reject</b> বাটন ব্যবহার করুন।\n"
                 "• কাস্টম প্ল্যান বানাতে <b>🛠️ Plan Make</b> চাপুন।\n"
                 "• ৩০টি অতিরিক্ত টুলের জন্য <b>⚙️ Others Option</b> ব্যবহার করুন।",
                 reply_keyboard=get_others_options_kb())

# --- Main Button & Dynamic Button Handler ---
MAIN_STATIC_BUTTONS = {
    "💎 Plans", "👤 Profile", "🤖 My Bots", "💰 Deposit",
    "📢 Updates Channel", "📤 Upload File", "📂 Check Files",
    "⚡ Bot Speed", "📞 Contact Owner", "📊 Statistics",
    "💳 Subscriptions", "📢 Broadcast", "🔒 Lock/Unlock",
    "🔒 Lock Bot", "🟢 Run All Code", "🟢 Running All Code",
    "👑 Admin Panel", "🟢 Run All", "⚙️ Others Option",
    "🛠️ Plan Make", "📥 Pending Deposits", "💳 Payment Setup",
    "📜 Pay History", "➕ ADD CHANNEL", "➖ REMOVE CHANNEL",
    "📦 Backup & Paste", "⚙️ System Toggles", "📜 Plan History",
    "🛡️ Audit Log", "✏️ Set bKash No", "✏️ Set Nagad No",
    "✏️ Set Rocket No", "💵 Set Min Deposit", "✏️ Set Trial Days",
    "✅ Joined - Check", "🔙 Back"
} | set(OTHERS_OPTION_BUTTONS)

def is_known_button_text(t):
    if not t:
        return False
    if t in MAIN_STATIC_BUTTONS:
        return True
    if t.startswith(("🤖 Bot: ", "🛒 Buy ", "💳 Pay ", "🔄 Restart ", "🛑 Stop ",
                   "📜 Logs ", "📊 Status ", "🔁 Auto-Restart:", "📥 Download ",
                   "🧹 Clear Log ", "📦 Backup ", "🗑️ Delete ", "❌ Remove ",
                   "📢 Join ")):
        return True
    if t in ("bKash: ON", "bKash: OFF", "Nagad: ON", "Nagad: OFF",
             "Rocket: ON", "Rocket: OFF", "Deposit System: ON", "Deposit System: OFF",
             "📢 Force Join: ON", "📢 Force Join: OFF",
             "💰 Deposit: ON", "💰 Deposit: OFF",
             "🔒 Lock Bot: ON", "🔒 Lock Bot: OFF") or t.startswith("🎁 Trial Days: "):
        return True
    return False

@bot.message_handler(func=lambda m: is_known_button_text(m.text))
def handle_btn(m):
    global bot_locked
    t = m.text.strip()
    uid = m.from_user.id

    if uid in banned_users and uid not in admin_ids:
        raw_send(m.chat.id, f"{PEM['no']} আপনি বট থেকে ব্যান হয়েছেন।")
        return

    touch_user_activity(uid)

    if t == "✅ Joined - Check":
        if user_joined_required_channels(uid):
            send_welcome(m.chat.id, uid, m.from_user.first_name, m.from_user.username)
        else:
            send_force_join_prompt(m.chat.id, uid)
        return

    if t.startswith("📢 Join "):
        ch_title = t[len("📢 Join "):].strip()
        found = next((x for x in get_force_channels() if x[1] == ch_title), None)
        if found:
            raw_send(m.chat.id, f"📢 Join <b>{found[1]}</b>:\n{found[2]}")
        return

    if uid not in admin_ids and not user_joined_required_channels(uid):
        send_force_join_prompt(m.chat.id, uid)
        return

    if t == "🔙 Back":
        user_states.pop(uid, None)
        raw_send(m.chat.id, f"{PEM['pin']} Main menu.", reply_keyboard=get_main_kb(uid))
        return

    if t in OTHERS_OPTION_BUTTONS:
        if uid not in admin_ids:
            raw_send(m.chat.id, f"{PEM['no']} Admin only.", reply_keyboard=get_main_kb(uid))
            return
        execute_others_option(t, m)
        return

    if t == "⚙️ Others Option":
        if uid not in admin_ids:
            raw_send(m.chat.id, f"{PEM['no']} Admin only.", reply_keyboard=get_main_kb(uid))
            return
        raw_send(m.chat.id,
                 f"⚙️ <b>Others Option (30 Tools)</b>\n\nনিচে ৩০টি কার্যকরী অপশন বাটন দেওয়া হলো:",
                 reply_keyboard=get_others_options_kb())
        return

    if t == "💎 Plans":
        show_plans_screen(m.chat.id, uid)
        return

    if t == "👤 Profile":
        show_profile_screen(m.chat.id, uid, m.from_user.first_name, m.from_user.username)
        return

    if t == "🤖 My Bots":
        show_my_bots_screen(m.chat.id, uid)
        return

    if t == "💰 Deposit":
        if not system_settings.get("deposit_enabled", True):
            raw_send(m.chat.id, "❌ ডিপোজিট সিস্টেম বর্তমানে বন্ধ আছে।", reply_keyboard=get_main_kb(uid))
            return
        min_dep = float(system_settings.get("min_deposit", 20.0))
        user_states[uid] = {"mode": "await_deposit_amount"}
        raw_send(m.chat.id,
                 f"💰 <b>Deposit Balance</b>\n\n"
                 f"সর্বনিম্ন ডিপোজিট সীমা: <b>৳{min_dep:.2f}</b>\n"
                 f"আপনি কত টাকা ডিপোজিট করতে চান তা লিখুন (বাতিল করতে /cancel বা 🔙 Back চাপুন):",
                 reply_keyboard=[[rbtn("🔙 Back", "6109360506319935223", "primary")]])
        return

    if t.startswith("🛒 Buy "):
        m_code = re.match(r"^🛒 Buy ([A-Za-z0-9_-]+)", t)
        code = m_code.group(1) if m_code else ""
        pl = plans_data.get(code)
        if not pl:
            raw_send(m.chat.id, "❌ প্ল্যানটি খুঁজে পাওয়া যায়নি।", reply_keyboard=get_main_kb(uid))
            return
        price = float(pl["price"])
        bal = get_balance(uid)
        if bal < price:
            need = round(price - bal, 2)
            raw_send(m.chat.id,
                     f"⚠️ <b>পর্যাপ্ত ব্যালেন্স নেই!</b>\n\n"
                     f"• প্ল্যান মূল্য: <b>৳{price:.2f}</b>\n"
                     f"• বর্তমান ব্যালেন্স: <b>৳{bal:.2f}</b>\n"
                     f"• আরও প্রয়োজন: <b>৳{need:.2f}</b>\n\n"
                     f"আগে <b>💰 Deposit</b> করে ব্যালেন্স অ্যাড করুন।",
                     reply_keyboard=get_main_kb(uid))
            return
        new_bal = round(bal - price, 2)
        set_balance_db(uid, new_bal)
        now = datetime.now()
        cur_exp = user_subscriptions.get(uid, {}).get('expiry')
        start = cur_exp if (cur_exp and cur_exp > now) else now
        new_exp = start + timedelta(days=int(pl["days"]))
        save_subscription(uid, new_exp, file_limit=int(pl["file_limit"]))
        order_id = "ORD" + str(uuid.uuid4())[:6].upper()
        save_plan_order_db(order_id, uid, code, pl["name"], pl["days"], pl["file_limit"], price, source="balance")
        raw_send(m.chat.id,
                 f"✅ <b>Plan Activated!</b>\n\n"
                 f"• Order ID: <code>{order_id}</code>\n"
                 f"• Plan: <b>{pl['name']}</b> (<code>{code}</code>)\n"
                 f"• Validity: <b>{pl['days']} days</b> (Exp: {new_exp:%Y-%m-%d})\n"
                 f"• Bot Limit: <b>{pl['file_limit']}</b>\n"
                 f"• Deducted: <b>৳{price:.2f}</b> | Remaining: <b>৳{new_bal:.2f}</b>",
                 reply_keyboard=get_main_kb(uid))
        for adm in set([int(ADMIN_ID)] + list(admin_ids)):
            try:
                bot.send_message(adm,
                                 f"🛒 <b>Plan Purchased!</b>\n"
                                 f"• User: <code>{uid}</code> (@{m.from_user.username or 'N/A'})\n"
                                 f"• Plan: <b>{pl['name']}</b> (<code>{code}</code>)\n"
                                 f"• Amount: <b>৳{price:.2f}</b> | Order: <code>{order_id}</code>",
                                 parse_mode='HTML')
            except Exception:
                pass
        return

    if t.startswith("💳 Pay "):
        method = t[len("💳 Pay "):].strip().upper()
        st = user_states.get(uid)
        if not st or st.get("mode") != "await_deposit_method":
            raw_send(m.chat.id, "⚠️ আগে <b>💰 Deposit</b> চেপে অ্যামাউন্ট দিন।", reply_keyboard=get_main_kb(uid))
            return
        amt = float(st["amount"])
        num_map = {
            "BKASH": system_settings.get("bkash_number", ""),
            "NAGAD": system_settings.get("nagad_number", ""),
            "ROCKET": system_settings.get("rocket_number", ""),
        }
        num = num_map.get(method) or "Not Configured"
        user_states[uid] = {"mode": "await_trx_id", "method": method, "amount": amt}
        raw_send(m.chat.id,
                 f"💳 <b>{method} Payment Instructions</b>\n\n"
                 f"• Number: <code>{num}</code>\n"
                 f"• Amount: <b>৳{amt:.2f}</b>\n\n"
                 f"Send Money সম্পন্ন করে নিচে <b>Transaction ID (TrxID)</b> পাঠান:",
                 reply_keyboard=[[rbtn("🔙 Back", "6109360506319935223", "primary")]])
        return

    if t.startswith("🤖 Bot: "):
        fn = t[len("🤖 Bot: "):].strip()
        if any(f[0] == fn for f in user_files.get(uid, [])):
            show_single_bot_panel(m.chat.id, uid, fn)
        else:
            raw_send(m.chat.id, "❌ বট ফাইলটি পাওয়া যায়নি।", reply_keyboard=get_main_kb(uid))
        return

    bot_action_prefixes = [
        ("🔄 Restart ", "restart"),
        ("🛑 Stop ", "stop"),
        ("📜 Logs ", "logs"),
        ("📊 Status ", "status"),
        ("📥 Download ", "download"),
        ("🧹 Clear Log ", "clearlog"),
        ("📦 Backup ", "backup"),
        ("🗑️ Delete ", "delete"),
    ]
    for prefix, act in bot_action_prefixes:
        if t.startswith(prefix):
            fn = t[len(prefix):].strip()
            owner = uid if any(f[0] == fn for f in user_files.get(uid, [])) else None
            if owner is None and uid in admin_ids:
                for o, fls in user_files.items():
                    if any(f[0] == fn for f in fls):
                        owner = o
                        break
            if owner is None:
                raw_send(m.chat.id, "❌ File not found.", reply_keyboard=get_main_kb(uid))
                return
            folder = get_user_folder(owner)
            fp = os.path.join(folder, fn)
            ft = next((f_t for f_n, f_t in user_files.get(owner, []) if f_n == fn),
                      'js' if fn.endswith('.js') else 'py')
            key = f"{owner}_{fn}"
            lp = os.path.join(folder, f"{os.path.splitext(fn)[0]}.log")

            if act == "restart":
                if is_bot_running(owner, fn):
                    pi = bot_scripts.get(key)
                    if pi:
                        kill_process_tree(pi)
                    bot_scripts.pop(key, None)
                    time.sleep(0.8)
                if not os.path.exists(fp):
                    raw_send(m.chat.id, "❌ Script file missing.", reply_keyboard=get_single_bot_kb(owner, fn))
                    return
                if ft == 'js':
                    threading.Thread(target=run_js_script, args=(fp, owner, folder, fn, m)).start()
                else:
                    threading.Thread(target=run_script, args=(fp, owner, folder, fn, m)).start()
                time.sleep(1.0)
                show_single_bot_panel(m.chat.id, owner, fn)
                return

            elif act == "stop":
                if is_bot_running(owner, fn):
                    pi = bot_scripts.get(key)
                    if pi:
                        kill_process_tree(pi)
                    bot_scripts.pop(key, None)
                raw_send(m.chat.id, f"🛑 Stopped <code>{fn}</code>.", reply_keyboard=get_single_bot_kb(owner, fn))
                show_single_bot_panel(m.chat.id, owner, fn)
                return

            elif act == "logs":
                if not os.path.exists(lp):
                    raw_send(m.chat.id, "📜 কোনো লগ ফাইল নেই।", reply_keyboard=get_single_bot_kb(owner, fn))
                    return
                try:
                    with open(lp, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    if not content.strip():
                        content = "(Empty log)"
                    if len(content) > 3500:
                        content = "...\n" + content[-3500:]
                    raw_send(m.chat.id, f"📜 <b>Logs:</b> <code>{fn}</code>\n<pre>{content}</pre>",
                             reply_keyboard=get_single_bot_kb(owner, fn))
                except Exception as e:
                    raw_send(m.chat.id, f"❌ Log read error: {e}", reply_keyboard=get_single_bot_kb(owner, fn))
                return

            elif act == "status":
                show_single_bot_panel(m.chat.id, owner, fn)
                return

            elif act == "download":
                if not os.path.exists(fp):
                    raw_send(m.chat.id, "❌ File missing on disk.", reply_keyboard=get_single_bot_kb(owner, fn))
                    return
                try:
                    with open(fp, "rb") as doc_f:
                        bot.send_document(m.chat.id, doc_f, visible_file_name=fn)
                except Exception as e:
                    raw_send(m.chat.id, f"❌ Download failed: {e}", reply_keyboard=get_single_bot_kb(owner, fn))
                return

            elif act == "clearlog":
                try:
                    with open(lp, "w", encoding="utf-8") as f:
                        f.write("")
                except Exception:
                    pass
                raw_send(m.chat.id, f"🧹 Cleared log for <code>{fn}</code>.", reply_keyboard=get_single_bot_kb(owner, fn))
                show_single_bot_panel(m.chat.id, owner, fn)
                return

            elif act == "backup":
                if not os.path.exists(fp):
                    raw_send(m.chat.id, "❌ Script missing.", reply_keyboard=get_single_bot_kb(owner, fn))
                    return
                zpath = None
                try:
                    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
                    zpath = tmp.name
                    tmp.close()
                    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
                        zf.write(fp, arcname=fn)
                    with open(zpath, "rb") as zf_in:
                        bot.send_document(m.chat.id, zf_in, visible_file_name=f"{os.path.splitext(fn)[0]}_backup.zip")
                except Exception as e:
                    raw_send(m.chat.id, f"❌ Backup failed: {e}", reply_keyboard=get_single_bot_kb(owner, fn))
                finally:
                    if zpath and os.path.exists(zpath):
                        try:
                            os.remove(zpath)
                        except Exception:
                            pass
                return

            elif act == "delete":
                if is_bot_running(owner, fn):
                    pi = bot_scripts.get(key)
                    if pi:
                        kill_process_tree(pi)
                    bot_scripts.pop(key, None)
                if os.path.exists(fp):
                    try:
                        os.remove(fp)
                    except Exception:
                        pass
                if os.path.exists(lp):
                    try:
                        os.remove(lp)
                    except Exception:
                        pass
                remove_user_file_db(owner, fn)
                raw_send(m.chat.id, f"🗑️ Deleted <code>{fn}</code>.")
                show_my_bots_screen(m.chat.id, owner)
                return

    if t.startswith("🔁 Auto-Restart:"):
        m_fn = re.search(r"\[(.+?)\]$", t)
        if m_fn:
            fn = m_fn.group(1).strip()
            owner = uid if any(f[0] == fn for f in user_files.get(uid, [])) else None
            if owner is None and uid in admin_ids:
                for o, fls in user_files.items():
                    if any(f[0] == fn for f in fls):
                        owner = o
                        break
            if owner is not None:
                cur_ar = is_auto_restart_enabled(owner, fn)
                set_auto_restart_db(owner, fn, not cur_ar)
                show_single_bot_panel(m.chat.id, owner, fn)
        return

    if t == "📢 Updates Channel":
        raw_send(m.chat.id, f"{PEM['msg']} <b>Updates Channel:</b>\n{UPDATE_CHANNEL}",
                 reply_keyboard=get_main_kb(uid))
    elif t == "📤 Upload File":
        limit = get_user_file_limit(uid)
        curr = get_user_file_count(uid)
        if curr >= limit:
            lim_str = str(limit) if limit != float('inf') else "Unlimited"
            raw_send(m.chat.id, f"{PEM['warn']} Limit ({curr}/{lim_str}).", reply_keyboard=get_main_kb(uid))
            return
        raw_send(m.chat.id,
                 f"{PEM['file']} Send .py, .js or .zip file.\n{PEM['warn']} Admin approval required.",
                 reply_keyboard=get_main_kb(uid))
    elif t == "📂 Check Files":
        files = user_files.get(uid, [])
        if not files:
            raw_send(m.chat.id, f"{PEM['file']} No files.", reply_keyboard=get_main_kb(uid))
            return
        msg = f"{PEM['file']} <b>Your files:</b>\n\n"
        kb = []
        for fn, ft in sorted(files):
            r = is_bot_running(uid, fn)
            icon = "🟢" if r else "🔴"
            msg += f"{icon} <code>{fn}</code> ({ft})\n"
            kb.append([rbtn(f"{'Stop' if r else 'Start'} {fn}", "6111726981760423576" if not r else "6311965254817423602",
                           "danger" if r else "success"),
                       rbtn(f"Delete {fn}", "6188343249791358585", "danger")])
        kb.append([rbtn("🔙 Back", "6109360506319935223", "primary")])
        raw_send(m.chat.id, msg, reply_keyboard=kb)
    elif t == "⚡ Bot Speed":
        t0 = time.time()
        wm = bot.reply_to(m, f"{PEM['wait']} Testing...", parse_mode='HTML')
        try:
            bot.send_chat_action(m.chat.id, 'typing')
            rt = round((time.time() - t0) * 1000, 2)
            st = f"{PEM['check']} Unlocked" if not bot_locked else f"{PEM['warn']} Locked"
            if uid == OWNER_ID:
                lvl = f"{PEM['crown']} Owner"
            elif uid in admin_ids:
                lvl = f"{PEM['admin']} Admin"
            elif uid in user_subscriptions and user_subscriptions[uid].get('expiry', datetime.min) > datetime.now():
                lvl = f"{PEM['check']} Premium"
            else:
                lvl = f"{PEM['user']} Free"
            bot.edit_message_text(f"{PEM['rocket']} Speed: {rt} ms\n🚦 {st}\n👤 {lvl}",
                                  m.chat.id, wm.message_id, parse_mode='HTML')
        except Exception:
            pass
    elif t == "📞 Contact Owner":
        raw_send(m.chat.id, f"{PEM['msg']} <b>Contact Owner:</b>\nhttps://t.me/{YOUR_USERNAME.replace('@', '')}",
                 reply_keyboard=get_main_kb(uid))
    elif t == "📊 Statistics":
        total_users = len(active_users)
        total_files = sum(len(f) for f in user_files.values())
        running = 0
        mine = 0
        for k, v in list(bot_scripts.items()):
            owner, _ = k.split('_', 1)
            if is_bot_running(int(owner), v['file_name']):
                running += 1
                if int(owner) == uid:
                    mine += 1
        msg = (f"{PEM['admin']} <b>Statistics:</b>\n\n"
               f"{PEM['user']} Users: {total_users}\n"
               f"{PEM['file']} Files: {total_files}\n"
               f"🟢 Running: {running}\n"
               f"{PEM['wait']} Pending: {len(pending_approvals)}\n")
        if uid in admin_ids:
            msg += f"🔒 Bot: {'Locked' if bot_locked else 'Unlocked'}\n🤖 Your Bots: {mine}"
        else:
            msg += f"🤖 Your Bots: {mine}"
        raw_send(m.chat.id, msg, reply_keyboard=get_main_kb(uid))
    elif t == "💳 Subscriptions":
        if uid not in admin_ids:
            raw_send(m.chat.id, f"{PEM['no']} Admin only.", reply_keyboard=get_main_kb(uid))
            return
        raw_send(m.chat.id,
                 f"{PEM['money']} <b>Subscription Management</b>\n\n"
                 f"Send: <code>addsub ID DAYS</code>\n"
                 f"Send: <code>removesub ID</code>\n"
                 f"Send: <code>checksub ID</code>",
                 reply_keyboard=get_main_kb(uid))
    elif t == "📢 Broadcast":
        if uid not in admin_ids:
            raw_send(m.chat.id, f"{PEM['no']} Admin only.", reply_keyboard=get_main_kb(uid))
            return
        msg = bot.reply_to(m, f"{PEM['msg']} Send broadcast message.\n/cancel to abort.", parse_mode='HTML')
        bot.register_next_step_handler(msg, process_broadcast)
    elif t in ["🔒 Lock/Unlock", "🔒 Lock Bot"]:
        if uid not in admin_ids:
            raw_send(m.chat.id, f"{PEM['no']} Admin only.", reply_keyboard=get_main_kb(uid))
            return
        bot_locked = not bot_locked
        save_system_setting_db("bot_locked", bot_locked)
        write_audit_log(uid, f"Toggled Lock Bot -> {bot_locked}")
        raw_send(m.chat.id, f"{'🔒 Bot locked.' if bot_locked else '🔓 Bot unlocked.'}", reply_keyboard=get_main_kb(uid))
    elif t in ["🟢 Run All Code", "🟢 Running All Code", "🟢 Run All"]:
        if uid not in admin_ids:
            raw_send(m.chat.id, f"{PEM['no']} Admin only.", reply_keyboard=get_main_kb(uid))
            return
        run_all_scripts(m)
    elif t == "👑 Admin Panel":
        if uid not in admin_ids:
            raw_send(m.chat.id, f"{PEM['no']} Admin only.", reply_keyboard=get_main_kb(uid))
            return
        raw_send(m.chat.id,
                 f"{PEM['crown']} <b>Admin Panel</b>\n\n"
                 f"Send: <code>addadmin ID</code>\n"
                 f"Send: <code>removeadmin ID</code>\n"
                 f"Send: <code>listadmins</code>",
                 reply_keyboard=get_admin_panel_kb(uid))

    elif t == "🛠️ Plan Make":
        if uid not in admin_ids:
            return
        user_states[uid] = {"mode": "plan_make_name"}
        raw_send(m.chat.id,
                 "🛠️ <b>Plan Maker (Step 1/4)</b>\n\nনতুন প্ল্যানের নাম লিখুন (/cancel বা 🔙 Back দিয়ে বাতিল করুন):",
                 reply_keyboard=[[rbtn("🔙 Back", "6109360506319935223", "primary")]])

    elif t == "📥 Pending Deposits":
        if uid not in admin_ids:
            return
        if not pending_deposits:
            raw_send(m.chat.id, "📥 কোনো পেন্ডিং ডিপোজিট রিকোয়েস্ট নেই।", reply_keyboard=get_admin_panel_kb(uid))
            return
        for dep_id, dep in list(pending_deposits.items()):
            markup = types.InlineKeyboardMarkup()
            markup.row(
                types.InlineKeyboardButton("✅ Approve", callback_data=f"dep_app:{dep_id}"),
                types.InlineKeyboardButton("❌ Reject", callback_data=f"dep_rej:{dep_id}")
            )
            card = (
                f"📥 <b>Pending Deposit</b>\n\n"
                f"• Deposit ID: <code>{dep_id}</code>\n"
                f"• User: @{dep.get('username') or 'N/A'} (<code>{dep['user_id']}</code>)\n"
                f"• Method: <b>{dep['method']}</b>\n"
                f"• Amount: <b>৳{dep['amount']:.2f}</b>\n"
                f"• TrxID: <code>{dep['trx_id']}</code>\n"
                f"• Time: {dep['created_at']}"
            )
            bot.send_message(m.chat.id, card, parse_mode='HTML', reply_markup=markup)

    elif t == "💳 Payment Setup":
        if uid not in admin_ids:
            return
        info = (
            f"💳 <b>Payment Setup</b>\n\n"
            f"• bKash ({'ON' if system_settings['bkash_enabled'] else 'OFF'}): <code>{system_settings['bkash_number'] or 'Not Set'}</code>\n"
            f"• Nagad ({'ON' if system_settings['nagad_enabled'] else 'OFF'}): <code>{system_settings['nagad_number'] or 'Not Set'}</code>\n"
            f"• Rocket ({'ON' if system_settings['rocket_enabled'] else 'OFF'}): <code>{system_settings['rocket_number'] or 'Not Set'}</code>\n"
            f"• Min Deposit: <b>৳{float(system_settings['min_deposit']):.2f}</b>\n"
            f"• Deposit System: <b>{'ON' if system_settings['deposit_enabled'] else 'OFF'}</b>"
        )
        raw_send(m.chat.id, info, reply_keyboard=get_payment_setup_kb())

    elif t in ("bKash: ON", "bKash: OFF"):
        if uid not in admin_ids:
            return
        if not system_settings["bkash_enabled"] and not system_settings["bkash_number"]:
            user_states[uid] = {"mode": "set_bkash_no", "next_enable": True}
            raw_send(m.chat.id, "✏️ আগে bKash নম্বর সেট করুন:")
            return
        new_st = not system_settings["bkash_enabled"]
        save_system_setting_db("bkash_enabled", new_st)
        write_audit_log(uid, f"bKash -> {'ON' if new_st else 'OFF'}")
        raw_send(m.chat.id, f"✅ bKash এখন <b>{'ON' if new_st else 'OFF'}</b>", reply_keyboard=get_payment_setup_kb())

    elif t in ("Nagad: ON", "Nagad: OFF"):
        if uid not in admin_ids:
            return
        if not system_settings["nagad_enabled"] and not system_settings["nagad_number"]:
            user_states[uid] = {"mode": "set_nagad_no", "next_enable": True}
            raw_send(m.chat.id, "✏️ আগে Nagad নম্বর সেট করুন:")
            return
        new_st = not system_settings["nagad_enabled"]
        save_system_setting_db("nagad_enabled", new_st)
        write_audit_log(uid, f"Nagad -> {'ON' if new_st else 'OFF'}")
        raw_send(m.chat.id, f"✅ Nagad এখন <b>{'ON' if new_st else 'OFF'}</b>", reply_keyboard=get_payment_setup_kb())

    elif t in ("Rocket: ON", "Rocket: OFF"):
        if uid not in admin_ids:
            return
        if not system_settings["rocket_enabled"] and not system_settings["rocket_number"]:
            user_states[uid] = {"mode": "set_rocket_no", "next_enable": True}
            raw_send(m.chat.id, "✏️ আগে Rocket নম্বর সেট করুন:")
            return
        new_st = not system_settings["rocket_enabled"]
        save_system_setting_db("rocket_enabled", new_st)
        write_audit_log(uid, f"Rocket -> {'ON' if new_st else 'OFF'}")
        raw_send(m.chat.id, f"✅ Rocket এখন <b>{'ON' if new_st else 'OFF'}</b>", reply_keyboard=get_payment_setup_kb())

    elif t in ("Deposit System: ON", "Deposit System: OFF", "💰 Deposit: ON", "💰 Deposit: OFF"):
        if uid not in admin_ids:
            return
        new_st = not system_settings["deposit_enabled"]
        save_system_setting_db("deposit_enabled", new_st)
        write_audit_log(uid, f"Deposit System -> {'ON' if new_st else 'OFF'}")
        kb = get_system_toggles_kb() if t.startswith("💰 Deposit:") else get_payment_setup_kb()
        raw_send(m.chat.id, f"✅ Deposit System এখন <b>{'ON' if new_st else 'OFF'}</b>", reply_keyboard=kb)

    elif t == "✏️ Set bKash No":
        if uid not in admin_ids:
            return
        user_states[uid] = {"mode": "set_bkash_no", "next_enable": False}
        raw_send(m.chat.id, "✏️ নতুন bKash নম্বর লিখুন:")

    elif t == "✏️ Set Nagad No":
        if uid not in admin_ids:
            return
        user_states[uid] = {"mode": "set_nagad_no", "next_enable": False}
        raw_send(m.chat.id, "✏️ নতুন Nagad নম্বর লিখুন:")

    elif t == "✏️ Set Rocket No":
        if uid not in admin_ids:
            return
        user_states[uid] = {"mode": "set_rocket_no", "next_enable": False}
        raw_send(m.chat.id, "✏️ নতুন Rocket নম্বর লিখুন:")

    elif t == "💵 Set Min Deposit":
        if uid not in admin_ids:
            return
        user_states[uid] = {"mode": "set_min_deposit"}
        raw_send(m.chat.id, "💵 নতুন সর্বনিম্ন ডিপোজিট অ্যামাউন্ট (৳) লিখুন:")

    elif t == "📜 Pay History":
        if uid not in admin_ids:
            return
        with DB_LOCK:
            conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
            rows = conn.execute(
                'SELECT deposit_id, user_id, method, amount, status, trx_id FROM deposits ORDER BY rowid DESC LIMIT 10'
            ).fetchall()
            conn.close()
        if not rows:
            raw_send(m.chat.id, "📜 কোনো ডিপোজিট হিস্ট্রি নেই।", reply_keyboard=get_admin_panel_kb(uid))
            return
        lines = ["📜 <b>Recent Deposits (Last 10):</b>\n"]
        for did, u, meth, amt, st_d, trx in rows:
            lines.append(f"• <code>{did}</code> | U:<code>{u}</code> | {meth} | <b>৳{amt:.2f}</b> | {st_d} | <code>{trx}</code>")
        raw_send(m.chat.id, "\n".join(lines), reply_keyboard=get_admin_panel_kb(uid))

    elif t == "➕ ADD CHANNEL":
        if uid not in admin_ids:
            return
        user_states[uid] = {"mode": "add_channel"}
        msg = bot.reply_to(m, f"{PEM['pin']} Channel/group @username বা public t.me link পাঠান।\n{PEM['warn']} Member check-এর জন্য bot-কে ওই channel/group-এ admin রাখুন।\n/cancel to abort.", parse_mode='HTML')
        bot.register_next_step_handler(msg, process_add_channel)

    elif t == "➖ REMOVE CHANNEL":
        if uid not in admin_ids:
            return
        channels = get_force_channels()
        if not channels:
            raw_send(m.chat.id, f"{PEM['warn']} No channels added.", reply_keyboard=get_admin_panel_kb(uid))
            return
        kb = [[rbtn(f"❌ Remove {title}", "6188343249791358585", "danger")] for _, title, _ in channels]
        kb.append([rbtn("🔙 Back", "6109360506319935223", "primary")])
        raw_send(m.chat.id, f"{PEM['rem']} <b>Select channel to remove:</b>", reply_keyboard=kb)

    elif t == "📦 Backup & Paste":
        if uid not in admin_ids:
            return
        zpath = None
        try:
            tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
            zpath = tmp.name
            tmp.close()
            with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
                if os.path.exists(DATABASE_PATH):
                    zf.write(DATABASE_PATH, arcname="bot_data.db")
                if os.path.exists(AUDIT_LOG_PATH):
                    zf.write(AUDIT_LOG_PATH, arcname="audit.log")
                if os.path.isdir(UPLOAD_BOTS_DIR):
                    for root_d, _, fnames in os.walk(UPLOAD_BOTS_DIR):
                        for fn_i in fnames:
                            full_p = os.path.join(root_d, fn_i)
                            arc_p = os.path.join("upload_bots", os.path.relpath(full_p, UPLOAD_BOTS_DIR))
                            zf.write(full_p, arcname=arc_p)
            with open(zpath, "rb") as zf_in:
                bot.send_document(m.chat.id, zf_in, visible_file_name=f"full_backup_{datetime.now():%Y%m%d_%H%M%S}.zip")
        except Exception as e:
            raw_send(m.chat.id, f"❌ Backup zip failed: {e}")
        finally:
            if zpath and os.path.exists(zpath):
                try:
                    os.remove(zpath)
                except Exception:
                    pass
        user_states[uid] = {"mode": "await_json_backup"}
        raw_send(m.chat.id,
                 "📦 রিস্টোর করতে চাইলে নতুন ব্যাকআপ <b>.zip ফাইল</b> পাঠান অথবা <b>JSON ব্যাকআপ টেক্সট</b> পেস্ট করুন (বাতিল করতে /cancel দিন):",
                 reply_keyboard=[[rbtn("🔙 Back", "6109360506319935223", "primary")]])

    elif t == "⚙️ System Toggles":
        if uid not in admin_ids:
            return
        info = (
            f"⚙️ <b>System Toggles</b>\n\n"
            f"• Force Join: <b>{'ON' if system_settings['force_join'] else 'OFF'}</b>\n"
            f"• Deposit System: <b>{'ON' if system_settings['deposit_enabled'] else 'OFF'}</b>\n"
            f"• Bot Lock: <b>{'ON' if system_settings['bot_locked'] else 'OFF'}</b>\n"
            f"• Free Trial Days: <b>{int(system_settings['trial_days'])}d</b>"
        )
        raw_send(m.chat.id, info, reply_keyboard=get_system_toggles_kb())

    elif t in ("📢 Force Join: ON", "📢 Force Join: OFF"):
        if uid not in admin_ids:
            return
        new_st = not system_settings["force_join"]
        save_system_setting_db("force_join", new_st)
        write_audit_log(uid, f"Force Join -> {'ON' if new_st else 'OFF'}")
        raw_send(m.chat.id, f"✅ Force Join এখন <b>{'ON' if new_st else 'OFF'}</b>", reply_keyboard=get_system_toggles_kb())

    elif t in ("🔒 Lock Bot: ON", "🔒 Lock Bot: OFF"):
        if uid not in admin_ids:
            return
        new_st = not system_settings["bot_locked"]
        bot_locked = new_st
        save_system_setting_db("bot_locked", new_st)
        write_audit_log(uid, f"Bot Lock -> {'ON' if new_st else 'OFF'}")
        raw_send(m.chat.id, f"✅ Bot Lock এখন <b>{'ON' if new_st else 'OFF'}</b>", reply_keyboard=get_system_toggles_kb())

    elif t.startswith("🎁 Trial Days: ") or t == "✏️ Set Trial Days":
        if uid not in admin_ids:
            return
        user_states[uid] = {"mode": "set_trial_days"}
        raw_send(m.chat.id, "🎁 নতুন ইউজারদের Free Trial কত দিন (days) হবে তা লিখুন (0 দিলে অফ):")

    elif t == "📜 Plan History":
        if uid not in admin_ids:
            return
        with DB_LOCK:
            conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
            rows = conn.execute(
                '''SELECT order_id, user_id, plan_code, days, file_limit, price, source
                   FROM plan_orders ORDER BY rowid DESC LIMIT 15'''
            ).fetchall()
            conn.close()
        if not rows:
            raw_send(m.chat.id, "📜 কোনো Plan Order হিস্ট্রি নেই।", reply_keyboard=get_admin_panel_kb(uid))
            return
        lines = ["📜 <b>Plan Orders (Last 15):</b>\n"]
        for oid, u, pcode, days, fl, prc, src in rows:
            lines.append(f"• <code>{oid}</code> | U:<code>{u}</code> | <code>{pcode}</code> | {days}d | Lim:{fl} | <b>৳{prc:.2f}</b> | {src}")
        raw_send(m.chat.id, "\n".join(lines), reply_keyboard=get_admin_panel_kb(uid))

    elif t == "🛡️ Audit Log":
        if uid != OWNER_ID:
            raw_send(m.chat.id, "❌ শুধুমাত্র Owner-এর জন্য।", reply_keyboard=get_admin_panel_kb(uid))
            return
        if not os.path.exists(AUDIT_LOG_PATH):
            raw_send(m.chat.id, "🛡️ Audit log খালি।", reply_keyboard=get_admin_panel_kb(uid))
            return
        with open(AUDIT_LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
            txt_a = f.read()
        if len(txt_a) > 3500:
            txt_a = "...\n" + txt_a[-3500:]
        raw_send(m.chat.id, f"🛡️ <b>Audit Log:</b>\n<pre>{txt_a or '(Empty)'}</pre>",
                 reply_keyboard=get_admin_panel_kb(uid))

# --- Remove Force Channel Buttons ---
@bot.message_handler(func=lambda m: m.text and m.text.startswith("❌ Remove "))
def handle_remove_force_channel(m):
    uid = m.from_user.id
    if uid not in admin_ids:
        return
    title = m.text[len("❌ Remove "):].strip()
    found = next((x for x in get_force_channels() if x[1] == title), None)
    if not found:
        raw_send(m.chat.id, f"{PEM['no']} Channel not found.", reply_keyboard=get_admin_panel_kb(uid))
        return
    remove_force_channel_db(found[0])
    write_audit_log(uid, f"Removed force channel {title}")
    raw_send(m.chat.id, f"{PEM['ok']} Removed: <b>{title}</b>", reply_keyboard=get_admin_panel_kb(uid))

# --- File Control via Text Commands ---
@bot.message_handler(func=lambda m: m.text and (
    m.text.startswith("Start ") or m.text.startswith("Stop ") or
    m.text.startswith("Delete ") or m.text.startswith("Logs ")
))
def handle_file_cmd(m):
    uid = m.from_user.id
    if uid in banned_users and uid not in admin_ids:
        return
    if uid not in admin_ids and not user_joined_required_channels(uid):
        send_force_join_prompt(m.chat.id, uid)
        return
    parts = m.text.split(maxsplit=1)
    if len(parts) != 2:
        return
    action = parts[0].lower()
    fn = parts[1].strip()

    owner = None
    for o, files in user_files.items():
        if any(f[0] == fn for f in files):
            owner = o
            break
    if owner is None:
        raw_send(m.chat.id, f"{PEM['no']} File not found.", reply_keyboard=get_main_kb(uid))
        return
    if not (uid == owner or uid in admin_ids):
        raw_send(m.chat.id, f"{PEM['no']} Not yours.", reply_keyboard=get_main_kb(uid))
        return

    folder = get_user_folder(owner)
    fp = os.path.join(folder, fn)
    ft = next((f[1] for f in user_files.get(owner, []) if f[0] == fn), 'py')
    key = f"{owner}_{fn}"

    if action == "start":
        if is_bot_running(owner, fn):
            raw_send(m.chat.id, f"{PEM['warn']} Already running.", reply_keyboard=get_main_kb(uid))
            return
        if not os.path.exists(fp):
            raw_send(m.chat.id, f"{PEM['no']} Missing file.", reply_keyboard=get_main_kb(uid))
            remove_user_file_db(owner, fn)
            return
        if ft == 'py':
            threading.Thread(target=run_script, args=(fp, owner, folder, fn, m)).start()
        elif ft == 'js':
            threading.Thread(target=run_js_script, args=(fp, owner, folder, fn, m)).start()
    elif action == "stop":
        if not is_bot_running(owner, fn):
            raw_send(m.chat.id, f"{PEM['warn']} Already stopped.", reply_keyboard=get_main_kb(uid))
            return
        pi = bot_scripts.get(key)
        if pi:
            kill_process_tree(pi)
        bot_scripts.pop(key, None)
        raw_send(m.chat.id, f"{PEM['ok']} Stopped {fn}.", reply_keyboard=get_main_kb(uid))
    elif action == "delete":
        if is_bot_running(owner, fn):
            pi = bot_scripts.get(key)
            if pi:
                kill_process_tree(pi)
            bot_scripts.pop(key, None)
        if os.path.exists(fp):
            os.remove(fp)
        lp = os.path.join(folder, f"{os.path.splitext(fn)[0]}.log")
        if os.path.exists(lp):
            os.remove(lp)
        remove_user_file_db(owner, fn)
        raw_send(m.chat.id, f"{PEM['ok']} Deleted {fn}.", reply_keyboard=get_main_kb(uid))
    elif action == "logs":
        lp = os.path.join(folder, f"{os.path.splitext(fn)[0]}.log")
        if not os.path.exists(lp):
            raw_send(m.chat.id, f"{PEM['no']} No logs.", reply_keyboard=get_main_kb(uid))
            return
        try:
            content = ""
            fs = os.path.getsize(lp)
            max_kb = 100
            max_msg = 3800
            if fs == 0:
                content = "(Empty)"
            elif fs > max_kb * 1024:
                with open(lp, 'rb') as f:
                    f.seek(-max_kb * 1024, os.SEEK_END)
                    content = f.read().decode('utf-8', errors='ignore')
                content = f"(Last {max_kb} KB)\n...\n" + content
            else:
                with open(lp, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            if len(content) > max_msg:
                content = content[-max_msg:]
                nl = content.find('\n')
                if nl != -1:
                    content = "...\n" + content[nl + 1:]
            if not content.strip():
                content = "(No content)"
            raw_send(m.chat.id, f"{PEM['file']} Logs for <b>{fn}</b>:\n<pre>{content}</pre>",
                     reply_keyboard=get_main_kb(uid))
        except Exception as e:
            raw_send(m.chat.id, f"{PEM['no']} Error: {e}", reply_keyboard=get_main_kb(uid))

# --- Text commands for admin panel ---
@bot.message_handler(func=lambda m: m.text and (
    m.text.startswith("addadmin ") or m.text.startswith("removeadmin ") or
    m.text.lower() == "listadmins" or
    m.text.startswith("addsub ") or m.text.startswith("removesub ") or
    m.text.startswith("checksub ")
))
def handle_admin_cmd(m):
    uid = m.from_user.id
    if uid not in admin_ids:
        raw_send(m.chat.id, f"{PEM['no']} Admin only.", reply_keyboard=get_main_kb(uid))
        return
    txt = m.text.strip()
    low = txt.lower()

    if low == "listadmins":
        lst = "\n".join(f"- <code>{a}</code> {'(Owner)' if a == OWNER_ID else ''}" for a in sorted(admin_ids))
        if not lst:
            lst = "(None)"
        raw_send(m.chat.id, f"{PEM['crown']} <b>Admins:</b>\n\n{lst}", reply_keyboard=get_main_kb(uid))
        return

    if low.startswith("addadmin "):
        if uid != OWNER_ID:
            raw_send(m.chat.id, f"{PEM['no']} Owner only.", reply_keyboard=get_main_kb(uid))
            return
        try:
            nid = int(txt.split()[1])
            if nid == OWNER_ID or nid in admin_ids:
                raw_send(m.chat.id, f"{PEM['warn']} Already admin.", reply_keyboard=get_main_kb(uid))
                return
            add_admin_db(nid)
            write_audit_log(uid, f"Added admin {nid}")
            raw_send(m.chat.id, f"{PEM['ok']} Added admin <code>{nid}</code>.", reply_keyboard=get_main_kb(uid))
            try:
                bot.send_message(nid, f"{PEM['crown']} You are now Admin!", parse_mode='HTML')
            except Exception:
                pass
        except Exception:
            raw_send(m.chat.id, f"{PEM['no']} Usage: addadmin ID", reply_keyboard=get_main_kb(uid))
        return

    if low.startswith("removeadmin "):
        if uid != OWNER_ID:
            raw_send(m.chat.id, f"{PEM['no']} Owner only.", reply_keyboard=get_main_kb(uid))
            return
        try:
            rid = int(txt.split()[1])
            if remove_admin_db(rid):
                write_audit_log(uid, f"Removed admin {rid}")
                raw_send(m.chat.id, f"{PEM['ok']} Removed admin <code>{rid}</code>.", reply_keyboard=get_main_kb(uid))
            else:
                raw_send(m.chat.id, f"{PEM['warn']} Not admin.", reply_keyboard=get_main_kb(uid))
        except Exception:
            raw_send(m.chat.id, f"{PEM['no']} Usage: removeadmin ID", reply_keyboard=get_main_kb(uid))
        return

    if low.startswith("addsub "):
        try:
            parts = txt.split()
            sid = int(parts[1])
            days = int(parts[2])
            if sid <= 0 or days <= 0:
                raise ValueError()
            ce = user_subscriptions.get(sid, {}).get('expiry')
            start = datetime.now()
            if ce and ce > start:
                start = ce
            ne = start + timedelta(days=days)
            save_subscription(sid, ne)
            save_plan_order_db("GFT" + str(uuid.uuid4())[:6].upper(), sid, "GIFT", f"Gift {days}d", days, SUBSCRIBED_USER_LIMIT, 0.0, source="admin_gift")
            write_audit_log(uid, f"Gifted {days}d sub to {sid}")
            raw_send(m.chat.id, f"{PEM['ok']} Sub added. Expiry: {ne:%Y-%m-%d}", reply_keyboard=get_main_kb(uid))
            try:
                bot.send_message(sid, f"{PEM['gift']} Sub active! Expires: {ne:%Y-%m-%d}.", parse_mode='HTML')
            except Exception:
                pass
        except Exception:
            raw_send(m.chat.id, f"{PEM['no']} Usage: addsub ID DAYS", reply_keyboard=get_main_kb(uid))
        return

    if low.startswith("removesub "):
        try:
            sid = int(txt.split()[1])
            remove_subscription_db(sid)
            write_audit_log(uid, f"Removed sub for {sid}")
            raw_send(m.chat.id, f"{PEM['ok']} Sub removed.", reply_keyboard=get_main_kb(uid))
            try:
                bot.send_message(sid, f"{PEM['no']} Subscription removed.", parse_mode='HTML')
            except Exception:
                pass
        except Exception:
            raw_send(m.chat.id, f"{PEM['no']} Usage: removesub ID", reply_keyboard=get_main_kb(uid))
        return

    if low.startswith("checksub "):
        try:
            sid = int(txt.split()[1])
            if sid in user_subscriptions:
                e = user_subscriptions[sid].get('expiry')
                if e:
                    if e > datetime.now():
                        dl = (e - datetime.now()).days
                        raw_send(m.chat.id, f"{PEM['ok']} <code>{sid}</code> active. Expires: {e:%Y-%m-%d} ({dl} days)", reply_keyboard=get_main_kb(uid))
                    else:
                        raw_send(m.chat.id, f"{PEM['warn']} <code>{sid}</code> expired.", reply_keyboard=get_main_kb(uid))
                        remove_subscription_db(sid)
                else:
                    raw_send(m.chat.id, f"{PEM['warn']} Expiry missing.", reply_keyboard=get_main_kb(uid))
            else:
                raw_send(m.chat.id, f"{PEM['user']} No sub.", reply_keyboard=get_main_kb(uid))
        except Exception:
            raw_send(m.chat.id, f"{PEM['no']} Usage: checksub ID", reply_keyboard=get_main_kb(uid))
        return

# --- General Text State Dispatcher ---
@bot.message_handler(func=lambda m: bool(m.text and m.from_user.id in user_states))
def handle_stateful_text(m):
    handle_user_state(m)

# --- Document Handler ---
@bot.message_handler(content_types=['document'])
def handle_doc(m):
    uid = m.from_user.id
    if uid in banned_users and uid not in admin_ids:
        raw_send(m.chat.id, f"{PEM['no']} আপনি বট থেকে ব্যান হয়েছেন।")
        return
    doc = m.document
    fn = doc.file_name or ""
    ext = os.path.splitext(fn)[1].lower()

    st = user_states.get(uid)
    if uid in admin_ids and st and st.get("mode") == "await_json_backup" and ext == ".zip":
        user_states.pop(uid, None)
        fi = bot.get_file(doc.file_id)
        content = bot.download_file(fi.file_path)
        restore_from_backup_zip(content, uid, m.chat.id)
        return

    if uid not in admin_ids and not user_joined_required_channels(uid):
        send_force_join_prompt(m.chat.id, uid)
        return
    if system_settings.get("bot_locked", bot_locked) and uid not in admin_ids:
        raw_send(m.chat.id, f"{PEM['warn']} Bot locked.", reply_keyboard=get_main_kb(uid))
        return
    limit = get_user_file_limit(uid)
    curr = get_user_file_count(uid)
    if curr >= limit:
        lim_str = str(limit) if limit != float('inf') else "Unlimited"
        raw_send(m.chat.id, f"{PEM['warn']} Limit ({curr}/{lim_str}).", reply_keyboard=get_main_kb(uid))
        return
    if not fn:
        raw_send(m.chat.id, f"{PEM['no']} No file name.", reply_keyboard=get_main_kb(uid))
        return
    if ext not in ['.py', '.js', '.zip']:
        raw_send(m.chat.id, f"{PEM['no']} Only .py, .js, .zip.", reply_keyboard=get_main_kb(uid))
        return
    if doc.file_size > 20 * 1024 * 1024:
        raw_send(m.chat.id, f"{PEM['no']} Max 20MB.", reply_keyboard=get_main_kb(uid))
        return
    try:
        wm = bot.reply_to(m, f"{PEM['wait']} Downloading `{fn}`...", parse_mode='HTML')
        fi = bot.get_file(doc.file_id)
        content = bot.download_file(fi.file_path)
        bot.edit_message_text(f"{PEM['ok']} Downloaded. Processing...", m.chat.id, wm.message_id, parse_mode='HTML')
        folder = get_user_folder(uid)
        if ext == '.zip':
            handle_zip(content, fn, m)
        else:
            fp = os.path.join(folder, fn)
            with open(fp, 'wb') as f:
                f.write(content)
            if ext == '.js':
                handle_js(fp, uid, folder, fn, m)
            elif ext == '.py':
                handle_py(fp, uid, folder, fn, m)
    except telebot.apihelper.ApiTelegramException as e:
        if "file is too big" in str(e).lower():
            raw_send(m.chat.id, f"{PEM['no']} File too large.", reply_keyboard=get_main_kb(uid))
        else:
            raw_send(m.chat.id, f"{PEM['no']} TG Error: {e}", reply_keyboard=get_main_kb(uid))
    except Exception as e:
        logger.error(f"doc err: {e}", exc_info=True)
        raw_send(m.chat.id, f"{PEM['no']} Error: {e}", reply_keyboard=get_main_kb(uid))

# --- Broadcast ---
def process_broadcast(m):
    uid = m.from_user.id
    if uid not in admin_ids:
        raw_send(m.chat.id, f"{PEM['no']} Admin only.", reply_keyboard=get_main_kb(uid))
        return
    if m.text and m.text.lower() == '/cancel':
        raw_send(m.chat.id, "Cancelled.", reply_keyboard=get_main_kb(uid))
        return
    content = m.text
    if not content and not (m.photo or m.video or m.document or m.sticker):
        raw_send(m.chat.id, f"{PEM['no']} Empty.", reply_keyboard=get_main_kb(uid))
        return
    raw_send(m.chat.id, f"{PEM['wait']} Broadcasting to {len(active_users)} users...", reply_keyboard=get_main_kb(uid))
    threading.Thread(target=do_broadcast, args=(content, m.chat.id)).start()

def do_broadcast(text, chat_id):
    sent = 0
    failed = 0
    blocked = 0
    users = list(active_users)
    total = len(users)
    for i, u in enumerate(users):
        try:
            bot.send_message(u, f"{PEM['bell']} {text}", parse_mode='HTML')
            sent += 1
        except telebot.apihelper.ApiTelegramException as e:
            ed = str(e).lower()
            if any(s in ed for s in ["blocked", "deactivated", "chat not found", "kicked", "restricted"]):
                blocked += 1
            else:
                failed += 1
        except Exception:
            failed += 1
        if (i + 1) % 25 == 0:
            time.sleep(1.5)
        elif i % 5 == 0:
            time.sleep(0.2)
    raw_send(chat_id, f"{PEM['ok']} <b>Broadcast Complete!</b>\n\n✅ Sent: {sent}\n❌ Failed: {failed}\n🚫 Blocked: {blocked}\n👥 Total: {total}")

# --- Run All Scripts ---
def run_all_scripts(m):
    uid = m.from_user.id
    chat_id = m.chat.id
    if uid not in admin_ids:
        return
    raw_send(chat_id, f"{PEM['wait']} Starting all scripts...", reply_keyboard=get_main_kb(uid))
    threading.Thread(target=run_all_scripts_bg, args=(chat_id,)).start()

def run_all_scripts_bg(chat_id):
    started = 0
    users_count = 0
    skipped = 0
    snapshot = dict(user_files)
    for tuid, files in snapshot.items():
        if not files:
            continue
        users_count += 1
        uf = get_user_folder(tuid)
        for fn, ft in files:
            if not is_bot_running(tuid, fn):
                fp = os.path.join(uf, fn)
                if os.path.exists(fp):
                    try:
                        if ft == 'py':
                            threading.Thread(target=run_script, args=(fp, tuid, uf, fn, _FakeMsg(chat_id))).start()
                            started += 1
                        elif ft == 'js':
                            threading.Thread(target=run_js_script, args=(fp, tuid, uf, fn, _FakeMsg(chat_id))).start()
                            started += 1
                        time.sleep(0.7)
                    except Exception:
                        skipped += 1
                else:
                    skipped += 1
    msg = f"{PEM['ok']} Started: {started}\n👥 Users: {users_count}\n"
    if skipped:
        msg += f"{PEM['warn']} Skipped: {skipped}\n"
    raw_send(chat_id, msg)

class _FakeMsg:
    def __init__(self, chat_id):
        self.chat = type('C', (), {'id': chat_id})()

# --- Cleanup ---
def cleanup():
    logger.warning("Shutting down...")
    for k in list(bot_scripts.keys()):
        if k in bot_scripts:
            kill_process_tree(bot_scripts[k])
atexit.register(cleanup)

# --- Main ---
if __name__ == '__main__':
    logger.info("=" * 40 + f"\n🤖 Bot Starting...\n🔑 Owner: {OWNER_ID}\n🛡️ Admins: {admin_ids}\n" + "=" * 40)
    keep_alive()
    threading.Thread(target=auto_restart_watchdog, daemon=True).start()
    logger.info("🚀 Polling started...")
    while True:
        try:
            bot.infinity_polling(logger_level=logging.INFO, timeout=60, long_polling_timeout=30)
        except requests.exceptions.ReadTimeout:
            logger.warning("ReadTimeout. 5s...")
            time.sleep(5)
        except requests.exceptions.ConnectionError as ce:
            logger.error(f"ConnError: {ce}. 15s...")
            time.sleep(15)
        except Exception as e:
            logger.critical(f"💥 Polling error: {e}", exc_info=True)
            time.sleep(30)
        finally:
            time.sleep(1)