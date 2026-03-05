#!/usr/bin/env python3
"""
OfertasFlash — Bot interactivo de Telegram.
Maneja comandos, referidos, VIP y publica ofertas automaticamente.

Corre 24/7 en VPS. Incluye scheduler para publicar ofertas en horarios.
"""

import asyncio
import json
import logging
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

# Telegram bot
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode

# AI
from groq import Groq

# Local
from config import (
    GROQ_API_KEY, GROQ_MODEL,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID,
    AMAZON_TAG, OFFERS_PER_RUN,
    PRODUCTS_FILE,
)
from database import (
    add_user, get_user, get_user_count, get_vip_count,
    set_vip, get_referral_count, get_stats, log_offer,
    get_expired_vips, remove_vip,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Config adicional ──
BOT_DIR = Path(__file__).parent
env_path = BOT_DIR / ".env"

def _env(key, default=""):
    """Lee variable de .env o environ."""
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if k.strip() == key and v.strip():
                    return v.strip()
    return os.environ.get(key, default)

# Canal VIP (privado) — se configura despues de crear el canal
VIP_CHANNEL_ID = _env("VIP_CHANNEL_ID", "")
VIP_INVITE_LINK = _env("VIP_INVITE_LINK", "")

# Stripe payment link para VIP
STRIPE_VIP_LINK = _env("STRIPE_VIP_LINK", "")

# Precio VIP
VIP_PRICE = "4.99"
VIP_CURRENCY = "EUR"

# Bot username (se rellena al arrancar)
BOT_USERNAME = ""


# ── Helpers ──

def amazon_link(asin: str) -> str:
    return f"https://www.amazon.es/dp/{asin}?tag={AMAZON_TAG}&linkCode=ogi&th=1"


def load_products() -> dict:
    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_history() -> list:
    history_file = BOT_DIR / "history.json"
    if history_file.exists():
        with open(history_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_history(history: list):
    history_file = BOT_DIR / "history.json"
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def select_products(n: int, vip_only: bool = False) -> list:
    data = load_products()
    history = load_history()
    recent = set(h["asin"] for h in history[-100:])

    all_prods = []
    for cat in data["categories"]:
        for prod in cat["products"]:
            if prod["asin"] not in recent:
                all_prods.append({**prod, "category": cat["name"], "emoji": cat["emoji"]})

    if len(all_prods) < n:
        all_prods = []
        for cat in data["categories"]:
            for prod in cat["products"]:
                all_prods.append({**prod, "category": cat["name"], "emoji": cat["emoji"]})

    random.shuffle(all_prods)

    # Variedad de categorias
    selected, used_cats = [], set()
    for p in all_prods:
        if p["category"] not in used_cats and len(selected) < n:
            selected.append(p)
            used_cats.add(p["category"])
    for p in all_prods:
        if p not in selected and len(selected) < n:
            selected.append(p)

    return selected[:n]


# ── AI Text Generation ──

SYSTEM_PROMPT = """Eres un experto en ofertas y chollos de Amazon España. Escribes mensajes CORTOS y ATRACTIVOS para Telegram.

REGLAS:
- Maximo 4-5 lineas
- Emojis estrategicos (🔥 ⚡ 💰 ✅ ⭐ 🎯)
- Menciona precio y por que es buena oferta
- Urgencia sutil (sin mentir)
- Tono cercano, español de España
- NO hashtags
- Nombre completo del producto"""


def generate_text(client: Groq, product: dict) -> str:
    try:
        r = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Producto: {product['name']}\nPrecio: {product['price_range']}\nCategoria: {product['category']}\n\nEscribe SOLO el mensaje (4-5 lineas). Primera linea = titulo con emoji. Ultima = llamada a la accion."},
            ],
            temperature=0.9,
            max_tokens=300,
        )
        return r.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"AI error: {e}")
        return f"🔥 {product['name']}\n\n💰 Precio: {product['price_range']}\n⭐ De los mas vendidos\n\n👉 Ver oferta"


# ── Telegram Commands ──

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start — bienvenida + tracking referido."""
    user = update.effective_user
    referred_by = None

    # Check deep link (referido)
    if context.args and context.args[0].startswith("ref_"):
        try:
            referred_by = int(context.args[0].replace("ref_", ""))
            if referred_by == user.id:
                referred_by = None
        except:
            pass

    add_user(user.id, user.username, user.first_name, referred_by)
    total = get_user_count()

    # Mensaje de bienvenida
    welcome = f"""🔥 <b>¡Bienvenido a OfertasFlash!</b>

Aqui encontraras las <b>mejores ofertas de Amazon</b> cada dia, seleccionadas por IA.

📢 <b>Canal gratuito:</b> 4 ofertas/dia
⭐ <b>Canal VIP ({VIP_PRICE}€/mes):</b> 20+ ofertas/dia + exclusivas + flash deals

👥 Somos ya <b>{total}</b> cazadores de ofertas"""

    if referred_by:
        welcome += f"\n\n🎁 Has sido invitado por un amigo. ¡Bienvenido!"

    keyboard = [
        [InlineKeyboardButton("📢 Canal Ofertas", url=f"https://t.me/{TELEGRAM_CHANNEL_ID.replace('@', '')}")],
        [InlineKeyboardButton(f"⭐ VIP — {VIP_PRICE}€/mes", callback_data="vip_info")],
        [InlineKeyboardButton("🎁 Invitar amigos (VIP gratis)", callback_data="referral")],
    ]

    await update.message.reply_text(
        welcome,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cmd_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /vip — info y enlace de pago."""
    await show_vip_info(update.effective_chat.id, context)


async def show_vip_info(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    text = f"""⭐ <b>Canal VIP OfertasFlash</b>

💎 ¿Que incluye?
• 20+ ofertas diarias (vs 4 gratis)
• Ofertas EXCLUSIVAS que no salen en el canal free
• Flash deals en tiempo real (chollos que duran horas)
• Alertas de bajadas de precio historicas
• Sin publicidad

💰 Solo <b>{VIP_PRICE}€/mes</b> — menos que un cafe

🎁 O invita a 3 amigos y consigue 1 semana VIP GRATIS"""

    keyboard = []
    if STRIPE_VIP_LINK:
        keyboard.append([InlineKeyboardButton(f"💳 Suscribirme — {VIP_PRICE}€/mes", url=STRIPE_VIP_LINK)])
    keyboard.append([InlineKeyboardButton("🎁 Invitar amigos (VIP gratis)", callback_data="referral")])

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cmd_invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /invite — enlace de referido."""
    await show_referral(update.effective_user.id, update.effective_chat.id, context)


async def show_referral(user_id: int, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    count = get_referral_count(user_id)
    remaining = 3 - (count % 3) if count % 3 != 0 else 3
    weeks_earned = count // 3

    link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"

    text = f"""🎁 <b>Programa de Referidos</b>

Tu enlace personal:
<code>{link}</code>

📊 <b>Tus stats:</b>
• Amigos invitados: <b>{count}</b>
• Semanas VIP ganadas: <b>{weeks_earned}</b>
• Faltan <b>{remaining}</b> invitaciones para la siguiente semana VIP

<b>¿Como funciona?</b>
1. Comparte tu enlace con amigos
2. Cada 3 amigos que se unan = 1 semana VIP GRATIS
3. ¡Sin limites! Mas amigos = mas VIP"""

    keyboard = [
        [InlineKeyboardButton("📤 Compartir enlace", url=f"https://t.me/share/url?url={link}&text=🔥 Las mejores ofertas de Amazon cada dia. Unete gratis!")],
    ]

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /stats — solo admin."""
    admin_id = int(os.environ.get("ADMIN_TELEGRAM_ID", "0"))
    if admin_id and update.effective_user.id != admin_id:
        await update.message.reply_text("No autorizado.")
        return
    stats = get_stats()
    user = get_user(update.effective_user.id)

    text = f"""📊 <b>Estadisticas OfertasFlash</b>

👥 Usuarios totales: <b>{stats['total_users']}</b>
⭐ Suscriptores VIP: <b>{stats['total_vip']}</b>
📦 Ofertas publicadas: <b>{stats['total_offers']}</b>
💰 Revenue total: <b>{stats['total_revenue']:.2f}€</b>
📈 Nuevos hoy: <b>{stats['today_users']}</b>"""

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja botones inline."""
    query = update.callback_query
    await query.answer()

    if query.data == "vip_info":
        await show_vip_info(query.message.chat_id, context)
    elif query.data == "referral":
        await show_referral(query.from_user.id, query.message.chat_id, context)


# ── Auto-Publisher ──

async def publish_offers(context: ContextTypes.DEFAULT_TYPE, channel: str, n: int, is_vip: bool = False):
    """Publica N ofertas en un canal."""
    if not GROQ_API_KEY:
        logger.warning("No GROQ_API_KEY, skipping publish")
        return

    client = Groq(api_key=GROQ_API_KEY)
    products = select_products(n)

    tag = "VIP ⭐" if is_vip else "FREE"
    logger.info(f"Publishing {n} offers to {channel} [{tag}]")

    for product in products:
        text = generate_text(client, product)
        link = amazon_link(product["asin"])

        if is_vip:
            full_text = f"⭐ <b>EXCLUSIVA VIP</b>\n\n{text}\n\n🛒 <a href=\"{link}\">Ver en Amazon</a>"
        else:
            full_text = f"{text}\n\n🛒 <a href=\"{link}\">Ver en Amazon</a>"
            # En canal free, añadir CTA viral
            full_text += f"\n\n💬 <i>¿Quieres mas ofertas? Unete al bot:</i> @{BOT_USERNAME}"

        # Botones
        buttons = [[InlineKeyboardButton("🛒 Ver en Amazon", url=link)]]
        if not is_vip:
            buttons.append([
                InlineKeyboardButton("⭐ Canal VIP", url=f"https://t.me/{BOT_USERNAME}?start=vip"),
                InlineKeyboardButton("📤 Compartir", url=f"https://t.me/share/url?url={link}&text=🔥 {product['name']} — {product['price_range']}"),
            ])

        try:
            await context.bot.send_message(
                chat_id=channel,
                text=full_text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(buttons),
                disable_web_page_preview=False,
            )
            log_offer(product["asin"], product["name"], "vip" if is_vip else "free")
            # Guardar en historial
            history = load_history()
            history.append({
                "asin": product["asin"],
                "name": product["name"],
                "sent_at": datetime.now(timezone.utc).isoformat(),
            })
            save_history(history)
            logger.info(f"  ✓ {product['name']}")
        except Exception as e:
            logger.error(f"  ✗ {product['name']}: {e}")

        await asyncio.sleep(2)  # Pausa entre mensajes


async def scheduled_free_offers(context: ContextTypes.DEFAULT_TYPE):
    """Publica ofertas en el canal gratuito (4 veces/dia, 5 por ronda = 20/dia)."""
    if TELEGRAM_CHANNEL_ID:
        await publish_offers(context, TELEGRAM_CHANNEL_ID, OFFERS_PER_RUN, is_vip=False)


async def scheduled_vip_offers(context: ContextTypes.DEFAULT_TYPE):
    """Publica ofertas en el canal VIP (mas frecuente, contenido exclusivo)."""
    if VIP_CHANNEL_ID:
        await publish_offers(context, VIP_CHANNEL_ID, OFFERS_PER_RUN, is_vip=True)


async def scheduled_cleanup(context: ContextTypes.DEFAULT_TYPE):
    """Limpia VIPs expirados."""
    expired = get_expired_vips()
    for uid in expired:
        remove_vip(uid)
        try:
            await context.bot.send_message(
                chat_id=uid,
                text="⏰ Tu suscripcion VIP ha expirado.\n\n¿Quieres renovar? Usa /vip o invita 3 amigos con /invite para conseguir 1 semana gratis.",
                parse_mode=ParseMode.HTML,
            )
        except:
            pass
        # Kick del canal VIP
        if VIP_CHANNEL_ID:
            try:
                await context.bot.ban_chat_member(VIP_CHANNEL_ID, uid)
                await context.bot.unban_chat_member(VIP_CHANNEL_ID, uid)
            except:
                pass
    if expired:
        logger.info(f"Cleaned {len(expired)} expired VIPs")


# ── Main ──

def main():
    global BOT_USERNAME

    if not TELEGRAM_BOT_TOKEN:
        print("[!] TELEGRAM_BOT_TOKEN no configurado. Ejecuta 'CONFIGURAR BOT.bat' primero.")
        sys.exit(1)

    # Crear app
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("vip", cmd_vip))
    app.add_handler(CommandHandler("invite", cmd_invite))
    app.add_handler(CommandHandler("referidos", cmd_invite))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Scheduler — Ofertas FREE (8:00, 12:00, 16:00, 20:00)
    job_queue = app.job_queue
    if TELEGRAM_CHANNEL_ID:
        for hour in [8, 12, 16, 20]:
            from datetime import time as dt_time
            job_queue.run_daily(scheduled_free_offers, time=dt_time(hour=hour, minute=0))
        logger.info(f"Scheduled FREE offers to {TELEGRAM_CHANNEL_ID} at 8,12,16,20h")

    # Scheduler — Ofertas VIP (cada 2 horas de 7 a 23)
    if VIP_CHANNEL_ID:
        for hour in range(7, 24, 2):
            from datetime import time as dt_time
            job_queue.run_daily(scheduled_vip_offers, time=dt_time(hour=hour, minute=30))
        logger.info(f"Scheduled VIP offers to {VIP_CHANNEL_ID} at 7:30-23:30 every 2h")

    # Cleanup diario a las 3:00
    from datetime import time as dt_time
    job_queue.run_daily(scheduled_cleanup, time=dt_time(hour=3, minute=0))

    # Get bot username
    import urllib.request
    try:
        r = urllib.request.urlopen(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe", timeout=10)
        data = json.loads(r.read().decode())
        if data.get("ok"):
            BOT_USERNAME = data["result"]["username"]
            logger.info(f"Bot: @{BOT_USERNAME}")
    except:
        pass

    print(f"""
╔══════════════════════════════════════════════════╗
║        OFERTAS FLASH — Bot Activo 🔥             ║
╠══════════════════════════════════════════════════╣
║  Bot: @{BOT_USERNAME:<40s} ║
║  Canal FREE: {TELEGRAM_CHANNEL_ID:<34s} ║
║  Canal VIP: {(VIP_CHANNEL_ID or 'No configurado'):<35s} ║
║  Ofertas FREE: 4x/dia (8,12,16,20h)             ║
║  Ofertas VIP: 9x/dia (cada 2h)                  ║
╚══════════════════════════════════════════════════╝
    """)

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
