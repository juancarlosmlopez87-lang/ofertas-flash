#!/usr/bin/env python3
"""
Script de configuracion rapida para OfertasFlash.
Te guia paso a paso para configurar el bot de Telegram.
"""

import json
import sys
import urllib.request

def test_bot_token(token: str) -> dict:
    """Verifica que el token del bot sea valido."""
    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        resp = urllib.request.urlopen(url, timeout=10)
        data = json.loads(resp.read().decode())
        if data.get("ok"):
            return data["result"]
    except Exception as e:
        print(f"Error: {e}")
    return {}


def test_channel(token: str, channel_id: str) -> bool:
    """Verifica que el bot pueda enviar mensajes al canal."""
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        params = json.dumps({
            "chat_id": channel_id,
            "text": "✅ OfertasFlash configurado correctamente! Las ofertas empezaran a llegar pronto.",
        }).encode()
        req = urllib.request.Request(url, data=params, method="POST",
                                     headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode())
        return data.get("ok", False)
    except Exception as e:
        print(f"Error: {e}")
    return False


def main():
    print("""
╔══════════════════════════════════════════════════╗
║          OFERTAS FLASH — Configuracion           ║
╚══════════════════════════════════════════════════╝

Este script te ayuda a configurar el bot de Telegram.
Necesitas hacer 3 cosas en Telegram:

1. Crear un bot con @BotFather
2. Crear un canal publico
3. Anadir el bot como administrador del canal
""")

    # Paso 1: Bot Token
    print("═══ PASO 1: Token del Bot ═══")
    print("1. Abre Telegram y busca @BotFather")
    print("2. Envia /newbot")
    print("3. Ponle nombre: OfertasFlash (o lo que quieras)")
    print("4. Ponle username: OfertasFlashES_bot (tiene que acabar en _bot)")
    print("5. BotFather te dara un token como: 123456789:ABCdefGHI...")
    print()

    token = input("Pega el token del bot aqui: ").strip()
    if not token:
        print("Token vacio. Saliendo.")
        sys.exit(1)

    bot_info = test_bot_token(token)
    if bot_info:
        print(f"\n✅ Bot verificado: @{bot_info['username']} ({bot_info['first_name']})")
    else:
        print("\n❌ Token invalido. Verifica que lo copiaste bien.")
        sys.exit(1)

    # Paso 2: Canal
    print("\n═══ PASO 2: Canal de Telegram ═══")
    print("1. Crea un canal publico en Telegram")
    print("   Nombre sugerido: OfertasFlash Amazon")
    print("   Username sugerido: @OfertasFlashES")
    print("2. En el canal, ve a Administradores")
    print("3. Anade el bot como administrador (con permiso de publicar)")
    print()

    channel = input("Username del canal (con @, ej: @OfertasFlashES): ").strip()
    if not channel.startswith("@"):
        channel = f"@{channel}"

    print(f"\nProbando envio a {channel}...")
    if test_channel(token, channel):
        print(f"✅ Mensaje enviado correctamente a {channel}!")
    else:
        print(f"❌ No se pudo enviar. Verifica que el bot es admin del canal.")
        sys.exit(1)

    # Guardar configuracion
    print(f"""
╔══════════════════════════════════════════════════╗
║              ¡TODO CONFIGURADO!                  ║
╚══════════════════════════════════════════════════╝

Guarda estas variables de entorno:

  export TELEGRAM_BOT_TOKEN="{token}"
  export TELEGRAM_CHANNEL_ID="{channel}"
  export GROQ_API_KEY="tu_key_de_groq"

Para probar manualmente:
  TELEGRAM_BOT_TOKEN="{token}" TELEGRAM_CHANNEL_ID="{channel}" GROQ_API_KEY="..." python ofertas_bot.py

Para el VPS (cron):
  0 8,12,16,20 * * * cd /root/ofertas/bot && TELEGRAM_BOT_TOKEN="{token}" TELEGRAM_CHANNEL_ID="{channel}" GROQ_API_KEY="..." python3 ofertas_bot.py >> /var/log/ofertas.log 2>&1
""")


if __name__ == "__main__":
    main()
