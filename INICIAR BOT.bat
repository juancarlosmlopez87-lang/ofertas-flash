@echo off
chcp 65001 >nul
title OfertasFlash - Bot 24/7
color 0A

echo.
echo ════════════════════════════════════════════════════
echo   OFERTAS FLASH — Bot activo
echo ════════════════════════════════════════════════════
echo.
echo   El bot publica ofertas automaticamente:
echo   Canal FREE: 4x/dia (8h, 12h, 16h, 20h)
echo   Canal VIP:  cada 2h (7:30 a 23:30)
echo.
echo   Tambien responde a comandos:
echo   /start - Bienvenida + tracking
echo   /vip   - Info suscripcion VIP
echo   /invite - Enlace de referidos
echo   /stats - Estadisticas (admin)
echo.
echo   Pulsa Ctrl+C para parar.
echo.
echo ════════════════════════════════════════════════════
echo.

cd /d "%~dp0bot"
python viral_bot.py

pause
