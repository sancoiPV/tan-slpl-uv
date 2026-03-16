@echo off
chcp 65001 > nul
title Servidor TAN Portatil - SLPL UV

echo.
echo =====================================================
echo   Servidor TAN portatil - SLPL Universitat de Valencia
echo   Model: projecte-aina/aina-translator-es-ca
echo   Port:  5001
echo =====================================================
echo.

:: Comprova que l'entorn virtual existeix
if not exist "C:\Users\santi\OneDrive\Documents\SLPL\taneu\venv_portatil\Scripts\activate.bat" (
    echo ERROR: Entorn virtual no trobat a C:\Users\santi\OneDrive\Documents\SLPL\taneu\venv_portatil
    echo Executa primer: instala_entorn.bat
    echo.
    pause
    exit /b 1
)

:: Comprova que el model existeix
if not exist "C:\Users\santi\OneDrive\Documents\SLPL\taneu\aina-translator-es-ca\model.bin" (
    echo ERROR: Model CTranslate2 no trobat a C:\Users\santi\OneDrive\Documents\SLPL\taneu\aina-translator-es-ca
    echo Executa primer: instala_entorn.bat
    echo.
    pause
    exit /b 1
)

:: Activa l'entorn virtual
echo Activant entorn virtual...
call C:\Users\santi\OneDrive\Documents\SLPL\taneu\venv_portatil\Scripts\activate.bat

:: Inicia el servidor Flask
echo Iniciant servidor...
echo (El model triga uns segons a carregar-se la primera vegada)
echo.
python C:\Users\santi\OneDrive\Documents\SLPL\taneu\portatil\server_portatil.py

:: Si el servidor s'atura (Ctrl+C o error), mostra un missatge
echo.
echo El servidor s'ha aturat.
pause
