@echo off
:: ADB Web Control - Startup Script
:: هذا الملف يشغّل الخادم بسهولة

title ADB Web Control Server
color 0A

echo.
echo ╔════════════════════════════════════════╗
echo ║   ADB Web Control - Scrcpy Edition     ║
echo ║      بدء تشغيل الخادم...              ║
echo ╚════════════════════════════════════════╝
echo.

:: التحقق من Python
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [✗] خطأ: Python غير مثبت
    echo يرجى تثبيت Python من: https://www.python.org
    pause
    exit /b 1
)

echo [✓] Python متوفر
echo.

:: التحقق من Flask
python -m pip show flask >nul 2>&1
if errorlevel 1 (
    echo [⚠] Flask غير مثبت، جاري التثبيت...
    python -m pip install flask
    echo [✓] تم تثبيت Flask
) else (
    echo [✓] Flask متوفر
)
echo.

:: التحقق من ADB
where adb >nul 2>&1
if errorlevel 1 (
    echo [✗] تحذير: ADB غير متوفر في PATH
    echo يرجى تثبيت Android SDK Platform Tools
) else (
    echo [✓] ADB متوفر
)
echo.

:: التحقق من Scrcpy
where scrcpy >nul 2>&1
if errorlevel 1 (
    echo [✗] تحذير: Scrcpy غير متوفر في PATH
    echo يرجى تثبيت Scrcpy من: https://github.com/Genymobile/scrcpy
) else (
    echo [✓] Scrcpy متوفر
)
echo.

echo ════════════════════════════════════════
echo [→] بدء تشغيل الخادم...
echo.
echo 🌐 افتح المتصفح على: http://localhost:5555
echo.
echo اضغط Ctrl+C لإيقاف الخادم
echo ════════════════════════════════════════
echo.

:: تشغيل الخادم
python server.py

pause
