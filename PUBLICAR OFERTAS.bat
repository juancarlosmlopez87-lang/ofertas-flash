@echo off
chcp 65001 >nul
title OfertasFlash - Publicando ofertas
color 0A

echo.
echo ╔══════════════════════════════════════════════════╗
echo ║       OFERTAS FLASH - Publicando ofertas          ║
echo ╚══════════════════════════════════════════════════╝
echo.

cd /d "%~dp0bot"
python ofertas_bot.py

echo.
pause
