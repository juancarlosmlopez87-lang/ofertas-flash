@echo off
chcp 65001 >nul
title OfertasFlash - Configuracion completa
color 0E

echo.
echo ════════════════════════════════════════════════════
echo   OFERTAS FLASH — Configuracion paso a paso
echo ════════════════════════════════════════════════════
echo.
echo ANTES de continuar, haz esto en Telegram (2 minutos):
echo.
echo   PASO 1 — Crear el Bot:
echo   1. Busca @BotFather en Telegram
echo   2. Escribe /newbot
echo   3. Nombre: OfertasFlash Amazon
echo   4. Username: OfertasFlashES_bot
echo   5. COPIA el token que te da
echo.
echo   PASO 2 — Crear canal GRATUITO (publico):
echo   1. Nuevo canal ^> Nombre: Ofertas Flash Amazon
echo   2. Publico ^> Username: OfertasFlashES
echo   3. Anade el bot como ADMIN (puede publicar)
echo.
echo   PASO 3 (OPCIONAL) — Crear canal VIP (privado):
echo   1. Nuevo canal ^> Nombre: OfertasFlash VIP
echo   2. PRIVADO
echo   3. Anade el bot como ADMIN
echo   4. Copia el invite link del canal
echo.
echo ════════════════════════════════════════════════════
echo.

set /p BOT_TOKEN="Token del bot (de BotFather): "
set /p CHANNEL_ID="Username canal gratuito (ej: @OfertasFlashES): "
set /p VIP_CHANNEL_ID="Chat ID canal VIP (dejar vacio si no tienes): "
set /p VIP_INVITE="Invite link canal VIP (dejar vacio si no tienes): "

echo.
echo Guardando configuracion...

(
echo GROQ_API_KEY=SET_YOUR_GROQ_KEY_HERE
echo TELEGRAM_BOT_TOKEN=%BOT_TOKEN%
echo TELEGRAM_CHANNEL_ID=%CHANNEL_ID%
echo VIP_CHANNEL_ID=%VIP_CHANNEL_ID%
echo VIP_INVITE_LINK=%VIP_INVITE%
echo STRIPE_VIP_LINK=
) > "%~dp0bot\.env"

echo.
echo Verificando bot...
cd /d "%~dp0bot"
python -c "from config import *; import urllib.request, json; r=urllib.request.urlopen(f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe',timeout=10); d=json.loads(r.read()); print(f'  Bot: @{d[\"result\"][\"username\"]}') if d.get('ok') else print('  ERROR: token invalido')"

echo.
echo Enviando mensaje de prueba al canal...
python -c "from config import *; import urllib.request, json; data=json.dumps({'chat_id':TELEGRAM_CHANNEL_ID,'text':'🔥 OfertasFlash activado! Las mejores ofertas de Amazon llegan pronto.\n\n⭐ Canal VIP con ofertas exclusivas: 4.99eur/mes\n🎁 Invita 3 amigos = 1 semana VIP gratis'}).encode(); req=urllib.request.Request(f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage',data=data,headers={'Content-Type':'application/json'}); r=urllib.request.urlopen(req,timeout=10); d=json.loads(r.read()); print('  Mensaje enviado OK!' if d.get('ok') else f'  ERROR: {d}')"

echo.
echo ════════════════════════════════════════════════════
echo.
echo   SIGUIENTE: Haz doble clic en "INICIAR BOT.bat"
echo   para arrancar el bot localmente, o
echo   "SUBIR A VPS.bat" para lanzarlo en el servidor 24/7
echo.
echo ════════════════════════════════════════════════════
echo.
pause
