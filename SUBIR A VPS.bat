@echo off
chcp 65001 >nul
title OfertasFlash - Subir a VPS
color 0B

echo.
echo ╔══════════════════════════════════════════════════╗
echo ║       OFERTAS FLASH - Subir a VPS Contabo         ║
echo ╚══════════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

echo Subiendo archivos al VPS...
python deploy_vps.py

echo.
pause
