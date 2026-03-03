#!/usr/bin/env python3
"""
OfertasFlash — Bot de Telegram que publica ofertas de Amazon automaticamente.
Usa Groq AI para generar descripciones atractivas y publica en un canal de Telegram.
Cada oferta incluye enlace de afiliado de Amazon.es.

Diseñado para correr en VPS con cron cada 4 horas.
"""

import json
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

from groq import Groq

from config import (
    GROQ_API_KEY, GROQ_MODEL,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID,
    AMAZON_TAG, OFFERS_PER_RUN,
    HISTORY_FILE, PRODUCTS_FILE,
)

# ── Helpers ──────────────────────────────────────────────────

def amazon_link(asin: str) -> str:
    return f"https://www.amazon.es/dp/{asin}?tag={AMAZON_TAG}&linkCode=ogi&th=1"


def amazon_image(asin: str) -> str:
    return f"https://ws-eu.amazon-adsystem.com/widgets/q?_encoding=UTF8&ASIN={asin}&Format=_SL250_&ID=AsinImage&MarketPlace=ES&ServiceVersion=20070822&WS=1&tag={AMAZON_TAG}"


def load_products() -> dict:
    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_history() -> list:
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_history(history: list):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


# ── Seleccionar productos para hoy ──────────────────────────

def select_products(n: int) -> list:
    """Selecciona N productos aleatorios de distintas categorias, evitando repetidos recientes."""
    data = load_products()
    history = load_history()
    recent_asins = set(h["asin"] for h in history[-100:])  # Ultimos 100 publicados

    all_products = []
    for cat in data["categories"]:
        for prod in cat["products"]:
            if prod["asin"] not in recent_asins:
                all_products.append({**prod, "category": cat["name"], "emoji": cat["emoji"]})

    # Si no hay suficientes sin repetir, resetear historial
    if len(all_products) < n:
        recent_asins = set()
        all_products = []
        for cat in data["categories"]:
            for prod in cat["products"]:
                all_products.append({**prod, "category": cat["name"], "emoji": cat["emoji"]})

    # Intentar variedad de categorias
    random.shuffle(all_products)
    selected = []
    used_cats = set()

    # Primero uno de cada categoria
    for p in all_products:
        if p["category"] not in used_cats and len(selected) < n:
            selected.append(p)
            used_cats.add(p["category"])

    # Completar con los restantes
    for p in all_products:
        if p not in selected and len(selected) < n:
            selected.append(p)

    return selected[:n]


# ── Generar texto con AI ─────────────────────────────────────

SYSTEM_PROMPT = """Eres un experto en ofertas y chollos de Amazon España. Tu trabajo es escribir mensajes CORTOS y ATRACTIVOS para un canal de Telegram de ofertas.

REGLAS:
- Maximo 4-5 lineas por mensaje
- Usa emojis estrategicamente (🔥 ⚡ 💰 ✅ ⭐ 🎯)
- Menciona el precio y por que es buena oferta
- Crea urgencia sutil (sin mentir)
- Tono cercano y directo
- En español de España
- NO uses hashtags
- Incluye siempre el nombre completo del producto"""


def generate_offer_text(client: Groq, product: dict) -> str:
    """Genera texto atractivo para una oferta."""
    prompt = f"""Escribe un mensaje de Telegram para esta oferta:

Producto: {product['name']}
Precio: {product['price_range']}
Categoria: {product['category']}

Escribe SOLO el texto del mensaje (4-5 lineas maximo). No incluyas enlaces ni el nombre de la tienda.
La primera linea debe ser un titulo llamativo con emoji.
La ultima linea debe ser una llamada a la accion como "Ver oferta" o "Pillalo antes de que suba"."""

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.9,
            max_tokens=300,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"  [!] Error AI: {e}")
        # Fallback: mensaje simple
        return (
            f"🔥 {product['name']}\n\n"
            f"💰 Precio: {product['price_range']}\n"
            f"⭐ Uno de los mas vendidos en su categoria\n\n"
            f"👉 Ver oferta en Amazon"
        )


# ── Enviar a Telegram ────────────────────────────────────────

def send_telegram_message(text: str, image_url: str = None) -> bool:
    """Envia un mensaje al canal de Telegram."""
    import urllib.request
    import urllib.parse

    base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

    try:
        if image_url:
            # Enviar con foto
            url = f"{base_url}/sendPhoto"
            params = urllib.parse.urlencode({
                "chat_id": TELEGRAM_CHANNEL_ID,
                "photo": image_url,
                "caption": text,
                "parse_mode": "HTML",
            }).encode()
        else:
            # Enviar solo texto
            url = f"{base_url}/sendMessage"
            params = urllib.parse.urlencode({
                "chat_id": TELEGRAM_CHANNEL_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            }).encode()

        req = urllib.request.Request(url, data=params, method="POST")
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read().decode())

        if result.get("ok"):
            return True
        else:
            print(f"  [!] Telegram error: {result}")
            return False

    except Exception as e:
        print(f"  [!] Error enviando a Telegram: {e}")
        return False


# ── Main ─────────────────────────────────────────────────────

def main():
    if not GROQ_API_KEY:
        print("[!] GROQ_API_KEY no configurada")
        sys.exit(1)

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        print("[!] TELEGRAM_BOT_TOKEN y TELEGRAM_CHANNEL_ID necesarios")
        print("    1. Habla con @BotFather en Telegram y crea un bot")
        print("    2. Crea un canal y anade el bot como administrador")
        print("    3. Exporta las variables:")
        print('       export TELEGRAM_BOT_TOKEN="123456:ABC..."')
        print('       export TELEGRAM_CHANNEL_ID="@tu_canal"')
        sys.exit(1)

    client = Groq(api_key=GROQ_API_KEY)
    products = select_products(OFFERS_PER_RUN)
    history = load_history()

    print(f"\n{'='*60}")
    print(f"  OFERTAS FLASH — Publicando {len(products)} ofertas")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    sent = 0
    for i, product in enumerate(products):
        print(f"[{i+1}/{len(products)}] {product['name']}...")

        # Generar texto
        text = generate_offer_text(client, product)

        # Anadir enlace de Amazon
        link = amazon_link(product["asin"])
        full_text = f"{text}\n\n🛒 <a href=\"{link}\">Ver en Amazon</a>"

        # Imagen del producto
        img_url = amazon_image(product["asin"])

        # Enviar
        if send_telegram_message(full_text, img_url):
            print(f"  OK: Enviado a {TELEGRAM_CHANNEL_ID}")
            sent += 1
            history.append({
                "asin": product["asin"],
                "name": product["name"],
                "sent_at": datetime.now(timezone.utc).isoformat(),
            })
        else:
            print(f"  FAIL: No se pudo enviar")

    # Guardar historial
    save_history(history)

    print(f"\n{'='*60}")
    print(f"  Resultado: {sent}/{len(products)} ofertas enviadas")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
