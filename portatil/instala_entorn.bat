@echo off
chcp 65001 > nul
echo.
echo =====================================================
echo   Instal.lacio entorn TAN portatil - SLPL UV
echo   Model: projecte-aina/aina-translator-es-ca
echo   Backend: CTranslate2 (CPU optimitzat)
echo =====================================================
echo.

:: ---- Comprova Python ----
echo [COMPROVACIO] Cercant Python 3.10+...
python --version > nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no trobat al PATH.
    echo Descarrega Python 3.10+ des de https://www.python.org/downloads/
    echo Assegura't de marcar "Add Python to PATH" durant la instal.lacio.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo    Python detectat: %PYVER%
echo.

:: ---- Crear directori base ----
echo [PAS 1/5] Creant estructura de directoris...
if not exist "C:\SLPL\TAN" (
    mkdir "C:\SLPL\TAN"
    echo    Creat: C:\SLPL\TAN
) else (
    echo    Ja existeix: C:\SLPL\TAN
)
echo.

:: ---- Copiar fitxers d'aquest script al directori destí ----
echo [PAS 2/5] Copiant fitxers de configuracio...
set SCRIPT_DIR=%~dp0
for %%f in ("%SCRIPT_DIR%descarrega_i_converteix.py" "%SCRIPT_DIR%server_portatil.py" "%SCRIPT_DIR%start_server_portatil.bat" "%SCRIPT_DIR%test_traduccio.py") do (
    if exist %%f (
        copy /Y %%f "C:\SLPL\TAN\" > nul
        echo    Copiat: %%~nxf
    )
)
echo.

:: ---- Crear entorn virtual ----
echo [PAS 3/5] Creant entorn virtual Python...
if exist "C:\SLPL\TAN\venv_portatil\Scripts\activate.bat" (
    echo    L'entorn virtual ja existeix, s'omiteix la creacio.
) else (
    python -m venv C:\SLPL\TAN\venv_portatil
    if errorlevel 1 (
        echo ERROR: No s'ha pogut crear l'entorn virtual.
        pause
        exit /b 1
    )
    echo    Entorn virtual creat a: C:\SLPL\TAN\venv_portatil
)
echo.

:: ---- Activar entorn virtual ----
call C:\SLPL\TAN\venv_portatil\Scripts\activate.bat

:: ---- Actualitzar pip ----
echo [PAS 4/5] Actualitzant pip i instal.lant biblioteques...
python -m pip install --upgrade pip --quiet
echo    pip actualitzat.

:: Instal.lar biblioteques una a una per poder detectar errors
echo    Instal.lant ctranslate2...
pip install ctranslate2 --quiet
if errorlevel 1 ( echo    AVIS: Error instal.lant ctranslate2 )

echo    Instal.lant sentencepiece...
pip install sentencepiece --quiet
if errorlevel 1 ( echo    AVIS: Error instal.lant sentencepiece )

echo    Instal.lant huggingface_hub...
pip install huggingface_hub --quiet
if errorlevel 1 ( echo    AVIS: Error instal.lant huggingface_hub )

echo    Instal.lant flask...
pip install flask --quiet
if errorlevel 1 ( echo    AVIS: Error instal.lant flask )

echo    Instal.lant requests...
pip install requests --quiet
if errorlevel 1 ( echo    AVIS: Error instal.lant requests )

echo    Totes les biblioteques instal.lades.
echo.

:: ---- Descarregar i convertir model ----
echo [PAS 5/5] Descarregant i convertint model AINA...
echo    Pot trigar 5-15 minuts segons la connexio a internet.
echo    Mida aproximada del model: ~300 MB
echo.
python C:\SLPL\TAN\descarrega_i_converteix.py
if errorlevel 1 (
    echo.
    echo ERROR durant la descarga/conversio del model.
    echo Revisa la connexio a internet i torna a executar aquest script.
    pause
    exit /b 1
)
echo.

:: ---- Fi ----
echo =====================================================
echo   INSTAL.LACIO COMPLETADA!
echo.
echo   Per iniciar el servidor:
echo     Fes doble clic a: C:\SLPL\TAN\start_server_portatil.bat
echo.
echo   Per provar la traduccio (amb el servidor en marcha):
echo     python C:\SLPL\TAN\test_traduccio.py
echo =====================================================
echo.
pause
