#!/usr/bin/env python3
"""Base de datos SQLite para OfertasFlash — usuarios, referidos, VIP, estadisticas."""

import sqlite3
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "ofertas.db"


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_at TEXT DEFAULT (datetime('now')),
            referred_by INTEGER,
            is_vip INTEGER DEFAULT 0,
            vip_until TEXT,
            stripe_customer_id TEXT,
            total_referrals INTEGER DEFAULT 0,
            total_clicks INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER NOT NULL,
            referred_id INTEGER NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            rewarded INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            stripe_session_id TEXT,
            amount_eur REAL,
            plan TEXT DEFAULT 'vip_monthly',
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS offer_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asin TEXT NOT NULL,
            product_name TEXT,
            channel TEXT DEFAULT 'free',
            sent_at TEXT DEFAULT (datetime('now')),
            clicks INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS daily_stats (
            date TEXT PRIMARY KEY,
            new_users INTEGER DEFAULT 0,
            new_vip INTEGER DEFAULT 0,
            offers_sent INTEGER DEFAULT 0,
            total_users INTEGER DEFAULT 0,
            revenue_eur REAL DEFAULT 0
        );
    """)
    conn.commit()
    conn.close()


# ── Usuarios ──

def add_user(telegram_id: int, username: str = None, first_name: str = None, referred_by: int = None):
    conn = get_db()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO users (telegram_id, username, first_name, referred_by) VALUES (?, ?, ?, ?)",
            (telegram_id, username, first_name, referred_by)
        )
        conn.commit()
        # Actualizar contador de referidos
        if referred_by:
            conn.execute("UPDATE users SET total_referrals = total_referrals + 1 WHERE telegram_id = ?", (referred_by,))
            conn.execute(
                "INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)",
                (referred_by, telegram_id)
            )
            conn.commit()
            # Auto-reward: 3 referidos = 1 semana VIP gratis
            check_referral_reward(conn, referred_by)
    finally:
        conn.close()


def get_user(telegram_id: int) -> dict:
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_count() -> int:
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return count


def get_vip_count() -> int:
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM users WHERE is_vip = 1").fetchone()[0]
    conn.close()
    return count


# ── VIP ──

def set_vip(telegram_id: int, months: int = 1):
    conn = get_db()
    user = conn.execute("SELECT vip_until FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    now = datetime.now(timezone.utc)

    if user and user["vip_until"]:
        try:
            current_end = datetime.fromisoformat(user["vip_until"])
            if current_end > now:
                new_end = current_end + timedelta(days=30 * months)
            else:
                new_end = now + timedelta(days=30 * months)
        except:
            new_end = now + timedelta(days=30 * months)
    else:
        new_end = now + timedelta(days=30 * months)

    conn.execute(
        "UPDATE users SET is_vip = 1, vip_until = ? WHERE telegram_id = ?",
        (new_end.isoformat(), telegram_id)
    )
    conn.commit()
    conn.close()


def set_vip_days(telegram_id: int, days: int = 7):
    """Dar VIP por X dias (para rewards de referidos)."""
    conn = get_db()
    now = datetime.now(timezone.utc)
    user = conn.execute("SELECT vip_until FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()

    if user and user["vip_until"]:
        try:
            current_end = datetime.fromisoformat(user["vip_until"])
            if current_end > now:
                new_end = current_end + timedelta(days=days)
            else:
                new_end = now + timedelta(days=days)
        except:
            new_end = now + timedelta(days=days)
    else:
        new_end = now + timedelta(days=days)

    conn.execute(
        "UPDATE users SET is_vip = 1, vip_until = ? WHERE telegram_id = ?",
        (new_end.isoformat(), telegram_id)
    )
    conn.commit()
    conn.close()


def get_expired_vips() -> list:
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    rows = conn.execute(
        "SELECT telegram_id FROM users WHERE is_vip = 1 AND vip_until < ?", (now,)
    ).fetchall()
    conn.close()
    return [r["telegram_id"] for r in rows]


def remove_vip(telegram_id: int):
    conn = get_db()
    conn.execute("UPDATE users SET is_vip = 0 WHERE telegram_id = ?", (telegram_id,))
    conn.commit()
    conn.close()


# ── Referidos ──

def check_referral_reward(conn, referrer_id: int):
    """Cada 3 referidos nuevos = 1 semana VIP gratis."""
    unrewarded = conn.execute(
        "SELECT COUNT(*) FROM referrals WHERE referrer_id = ? AND rewarded = 0",
        (referrer_id,)
    ).fetchone()[0]

    if unrewarded >= 3:
        # Marcar 3 como recompensados
        ids = conn.execute(
            "SELECT id FROM referrals WHERE referrer_id = ? AND rewarded = 0 LIMIT 3",
            (referrer_id,)
        ).fetchall()
        for r in ids:
            conn.execute("UPDATE referrals SET rewarded = 1 WHERE id = ?", (r["id"],))
        conn.commit()
        # Dar VIP
        set_vip_days(referrer_id, 7)


def get_referral_count(telegram_id: int) -> int:
    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (telegram_id,)
    ).fetchone()[0]
    conn.close()
    return count


# ── Pagos ──

def add_payment(telegram_id: int, stripe_session_id: str, amount: float, plan: str = "vip_monthly"):
    conn = get_db()
    conn.execute(
        "INSERT INTO payments (telegram_id, stripe_session_id, amount_eur, plan, status) VALUES (?, ?, ?, ?, 'completed')",
        (telegram_id, stripe_session_id, amount, plan)
    )
    conn.commit()
    conn.close()


# ── Stats ──

def log_offer(asin: str, product_name: str, channel: str = "free"):
    conn = get_db()
    conn.execute(
        "INSERT INTO offer_stats (asin, product_name, channel) VALUES (?, ?, ?)",
        (asin, product_name, channel)
    )
    conn.commit()
    conn.close()


def get_stats() -> dict:
    conn = get_db()
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_vip = conn.execute("SELECT COUNT(*) FROM users WHERE is_vip = 1").fetchone()[0]
    total_offers = conn.execute("SELECT COUNT(*) FROM offer_stats").fetchone()[0]
    total_revenue = conn.execute("SELECT COALESCE(SUM(amount_eur), 0) FROM payments WHERE status = 'completed'").fetchone()[0]
    today = datetime.now().strftime("%Y-%m-%d")
    today_users = conn.execute("SELECT COUNT(*) FROM users WHERE joined_at LIKE ?", (f"{today}%",)).fetchone()[0]
    conn.close()
    return {
        "total_users": total_users,
        "total_vip": total_vip,
        "total_offers": total_offers,
        "total_revenue": total_revenue,
        "today_users": today_users,
    }


# Inicializar al importar
init_db()
