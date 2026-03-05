#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sube OfertasFlash al VPS y lanza bot 24/7 + webhook Stripe."""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import os
import paramiko
from pathlib import Path

VPS_HOST = os.environ.get("VPS_HOST", "62.171.128.42")
VPS_USER = os.environ.get("VPS_USER", "root")
VPS_PASS = os.environ.get("VPS_PASS", "")
if not VPS_PASS:
    VPS_PASS = input("VPS password: ").strip()
VPS_PATH = "/root/ofertas/bot"

BOT_DIR = Path(__file__).parent / "bot"

def main():
    print(f"Conectando a {VPS_HOST}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASS, timeout=15)
    sftp = ssh.open_sftp()

    # Crear directorio
    for d in ["/root/ofertas", VPS_PATH]:
        try:
            sftp.mkdir(d)
        except:
            pass

    # Subir archivos del bot
    files = [
        "viral_bot.py", "ofertas_bot.py", "config.py", "database.py",
        "stripe_webhook.py", "products.json",
        ".env", "requirements.txt",
    ]
    for f in files:
        local = BOT_DIR / f
        if local.exists():
            print(f"  Subiendo {f}...")
            sftp.put(str(local), f"{VPS_PATH}/{f}")

    # Instalar dependencias (con --break-system-packages para Ubuntu 24.04)
    print("\nInstalando dependencias...")
    stdin, stdout, stderr = ssh.exec_command(
        f"cd {VPS_PATH} && pip3 install --break-system-packages -r requirements.txt 2>&1 | tail -5"
    )
    print(stdout.read().decode().strip())

    # Matar procesos anteriores
    print("\nReiniciando servicios...")
    ssh.exec_command("screen -X -S ofertas_bot quit 2>/dev/null")
    ssh.exec_command("screen -X -S ofertas_webhook quit 2>/dev/null")

    import time
    time.sleep(2)

    # Lanzar bot principal (24/7, maneja comandos + scheduler de ofertas)
    ssh.exec_command(f"screen -dmS ofertas_bot bash -c 'cd {VPS_PATH} && python3 viral_bot.py >> /var/log/ofertas_bot.log 2>&1'")
    print("  [OK] Bot principal lanzado (screen: ofertas_bot)")

    # Lanzar webhook Stripe (puerto 5050)
    ssh.exec_command(f"screen -dmS ofertas_webhook bash -c 'cd {VPS_PATH} && python3 stripe_webhook.py >> /var/log/ofertas_webhook.log 2>&1'")
    print("  [OK] Webhook Stripe lanzado (screen: ofertas_webhook, puerto 5050)")

    # Eliminar cron viejo (ya no se necesita, el bot tiene scheduler interno)
    stdin, stdout, stderr = ssh.exec_command("crontab -l 2>/dev/null")
    current_cron = stdout.read().decode()
    if "ofertas_bot.py" in current_cron:
        new_cron = "\n".join(l for l in current_cron.splitlines() if "ofertas_bot.py" not in l)
        ssh.exec_command(f"echo '{new_cron}' | crontab -")
        print("  [OK] Cron viejo eliminado (scheduler interno del bot)")

    # Verificar
    print("\nVerificando...")
    stdin, stdout, stderr = ssh.exec_command("screen -ls 2>/dev/null | grep ofertas")
    screens = stdout.read().decode().strip()
    print(f"  Screens activos:\n{screens}")

    sftp.close()
    ssh.close()

    print(f"""
{'='*60}
  OfertasFlash desplegado en VPS!

  Bot 24/7: screen -r ofertas_bot
  Webhook:  screen -r ofertas_webhook
  Logs:     tail -f /var/log/ofertas_bot.log

  El bot publica automaticamente:
  - Canal FREE: 4x/dia (8,12,16,20h) = 20 ofertas
  - Canal VIP:  9x/dia (cada 2h) = 45 ofertas

  Webhook Stripe: http://{VPS_HOST}:5050/webhook/stripe
{'='*60}
""")


if __name__ == "__main__":
    main()
