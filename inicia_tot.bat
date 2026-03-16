@echo off
chcp 65001 > nul
echo.
echo =====================================================
echo   TAN · SLPL · Universitat de València
echo   Iniciant tots els servidors...
echo =====================================================
echo.

:: ---- Servidor 1: Frontend (port 3000) ----
echo [1/3] Iniciant servidor frontend (port 3000)...
start "TAN — Frontend (port 3000)" cmd /k "cd /d C:\Users\santi\OneDrive\Documents\SLPL\taneu\frontend && python -m http.server 3000"
echo    OK.
echo.

:: ---- Servidor 2: Uvicorn API (port 8000) ----
echo [2/3] Iniciant servidor Uvicorn API (port 8000)...
start "TAN — Uvicorn API (port 8000)" cmd /k "cd /d C:\Users\santi\OneDrive\Documents\SLPL\taneu && .venv\Scripts\activate && uvicorn webapp.api:app --host 0.0.0.0 --port 8000 --reload"
echo    OK.
echo.

:: ---- Espera 3 seg perque uvicorn carregue el model ----
echo    Esperant 3 segons per a carrega del model...
timeout /t 3 /nobreak >nul

:: ---- Servidor 3: CTranslate2 CPU (port 5001) ----
echo [3/3] Iniciant servidor CTranslate2 CPU (port 5001)...
start "TAN — CTranslate2 CPU (port 5001)" cmd /k "cd /d C:\Users\santi\OneDrive\Documents\SLPL\taneu && call portatil\start_server_portatil.bat"
echo    OK.
echo.

echo =====================================================
echo   Tots els servidors iniciats!
echo.
echo   Frontend:  http://localhost:3000
echo   API:       http://localhost:8000
echo   CT2/CPU:   http://localhost:5001
echo.
echo   Tanca aquesta finestra quan vulgues.
echo =====================================================
echo.
pause
