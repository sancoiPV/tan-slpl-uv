@echo off
chcp 65001 > nul
echo.
echo  =====================================================
echo   Motor TAN SLPL-UV - Inici del servei (automatic)
echo  =====================================================
echo.

set BASE=C:\Users\santi\OneDrive\Documents\SLPL\taneu

:: ── PAS 1: Backend FastAPI ─────────────────────────────────────────────────
echo  [1/3] Iniciant backend FastAPI al port 8000...
start "TAN Backend" cmd /k "cd /d %BASE% && .venv\Scripts\activate && python -m uvicorn webapp.api:app --host 0.0.0.0 --port 8000"
:: Espera que uvicorn arranque del tot
timeout /t 6 /nobreak > nul

:: ── PAS 2: Tunel ngrok ────────────────────────────────────────────────────
echo  [2/3] Iniciant tunel ngrok...
start "TAN ngrok" cmd /k "%BASE%\ngrok.exe http 8000"
:: Espera que ngrok publique la URL (sol trigar 3-5 seg)
timeout /t 7 /nobreak > nul

:: ── PAS 3: Actualitza config.js i publica a Netlify ──────────────────────
echo  [3/3] Detectant URL ngrok i actualitzant Netlify...
echo        (pot trigar fins a 30 segons)
echo.
cd /d %BASE%
call .venv\Scripts\activate
python actualitza_ngrok.py

:: ── Resultat ──────────────────────────────────────────────────────────────
echo.
echo  =====================================================
echo   Sistema llest. Netlify redesplegarà en ~30-60 seg.
echo.
echo   Interfície pública:
echo     https://tan-slpl-uv.netlify.app
echo.
echo   Endpoints actius (detecció automàtica al frontend):
echo     1. Servidor UV (ngrok)  — URL actualitzada ara
echo     2. Servidor UV (VPN)    — si connectes via VPN UV
echo     3. Motor local          — http://127.0.0.1:5001
echo  =====================================================
echo.
pause
