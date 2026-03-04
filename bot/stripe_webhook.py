#!/usr/bin/env python3
"""
Webhook de Stripe para OfertasFlash VIP.
Recibe pagos y activa VIP automaticamente via Telegram.

Corre en VPS en el puerto 5050.
"""

import json
import os
import sys
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# Cargar .env
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            if v.strip() and not os.environ.get(k.strip()):
                os.environ[k.strip()] = v.strip()

from database import set_vip, add_payment, get_user

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
VIP_INVITE_LINK = os.environ.get("VIP_INVITE_LINK", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

PORT = 5050


def send_telegram(chat_id: int, text: str):
    """Envia mensaje via Telegram Bot API."""
    try:
        data = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"[!] Telegram send error: {e}")


class WebhookHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        if self.path != "/webhook/stripe":
            self.send_response(404)
            self.end_headers()
            return

        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len)

        try:
            event = json.loads(body.decode())
        except:
            self.send_response(400)
            self.end_headers()
            return

        event_type = event.get("type", "")
        print(f"[Stripe] {event_type}")

        if event_type == "checkout.session.completed":
            session = event["data"]["object"]
            # Extraer telegram_id de metadata
            metadata = session.get("metadata", {})
            telegram_id = metadata.get("telegram_id")
            amount = (session.get("amount_total", 0) or 0) / 100

            if telegram_id:
                telegram_id = int(telegram_id)
                # Activar VIP
                set_vip(telegram_id, months=1)
                add_payment(telegram_id, session.get("id", ""), amount)

                # Notificar al usuario
                msg = f"⭐ <b>¡Tu VIP esta activo!</b>\n\nYa tienes acceso al canal exclusivo con 20+ ofertas diarias."
                if VIP_INVITE_LINK:
                    msg += f"\n\n👉 <a href='{VIP_INVITE_LINK}'>Unirte al canal VIP</a>"
                send_telegram(telegram_id, msg)

                print(f"  ✓ VIP activado para {telegram_id} ({amount}€)")

        elif event_type == "customer.subscription.deleted":
            # Suscripcion cancelada
            sub = event["data"]["object"]
            metadata = sub.get("metadata", {})
            telegram_id = metadata.get("telegram_id")
            if telegram_id:
                from database import remove_vip
                remove_vip(int(telegram_id))
                send_telegram(int(telegram_id),
                    "⏰ Tu suscripcion VIP ha terminado.\n\nPuedes renovar con /vip o invitar amigos con /invite.")

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"ok": true}')

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OfertasFlash webhook OK")

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")


def main():
    print(f"[Stripe Webhook] Escuchando en puerto {PORT}")
    print(f"  URL: http://62.171.128.42:{PORT}/webhook/stripe")
    server = HTTPServer(("0.0.0.0", PORT), WebhookHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
