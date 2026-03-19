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
SET PYTHON_CMD=
WHERE python >/dev/null 2>&1 && SET PYTHON_CMD=python
IF NOT DEFINED PYTHON_CMD (
    IF EXIST "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
        SET PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python313\python.exe
    )
)
IF NOT DEFINED PYTHON_CMD (
    IF EXIST "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
        SET PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
    )
)
IF NOT DEFINED PYTHON_CMD (
    IF EXIST "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
        SET PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
    )
)
IF NOT DEFINED PYTHON_CMD (
    IF EXIST "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
        SET PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python310\python.exe
    )
)
IF NOT DEFINED PYTHON_CMD (
    IF EXIST "C:\Python311\python.exe" SET PYTHON_CMD=C:\Python311\python.exe
)
IF NOT DEFINED PYTHON_CMD (
    ECHO ERROR: Python no trobat.
    ECHO Descarrega'l de https://www.python.org/downloads/
    PAUSE
    EXIT /B 1
)
FOR /f "tokens=2" %%v IN ('"%PYTHON_CMD%" --version 2^>^&1') DO SET PYVER=%%v
ECHO    Python trobat: %PYTHON_CMD%
ECHO    Versio: %PYVER%
echo.

:: ---- Crear directori base ----
echo [PAS 1/5] Creant estructura de directoris...
if not exist "C:\Users\santi\OneDrive\Documents\SLPL\taneu" (
    mkdir "C:\Users\santi\OneDrive\Documents\SLPL\taneu"
    echo    Creat: C:\Users\santi\OneDrive\Documents\SLPL\taneu
) else (
    echo    Ja existeix: C:\Users\santi\OneDrive\Documents\SLPL\taneu
)
echo.

:: ---- Copiar fitxers d'aquest script al directori desti ----
echo [PAS 2/5] Copiant fitxers de configuracio...
set SCRIPT_DIR=%~dp0
for %%f in ("%SCRIPT_DIR%descarrega_i_converteix.py" "%SCRIPT_DIR%server_portatil.py" "%SCRIPT_DIR%start_server_portatil.bat" "%SCRIPT_DIR%test_traduccio.py") do (
    if exist %%f (
        copy /Y %%f "C:\Users\santi\OneDrive\Documents\SLPL\taneu\" > nul
        echo    Copiat: %%~nxf
    )
)
echo.

:: ---- Crear entorn virtual ----
echo [PAS 3/5] Creant entorn virtual Python...
if exist "C:\Users\santi\OneDrive\Documents\SLPL\taneu\venv_portatil\Scripts\activate.bat" (
    echo    L'entorn virtual ja existeix, s'omiteix la creacio.
) else (
    "%PYTHON_CMD%" -m venv C:\Users\santi\OneDrive\Documents\SLPL\taneu\venv_portatil
    if errorlevel 1 (
        echo ERROR: No s'ha pogut crear l'entorn virtual.
        pause
        exit /b 1
    )
    echo    Entorn virtual creat a: C:\Users\santi\OneDrive\Documents\SLPL\taneu\venv_portatil
)
echo.

:: ---- Activar entorn virtual ----
call C:\Users\santi\OneDrive\Documents\SLPL\taneu\venv_portatil\Scripts\activate.bat

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

:: ---- Preparar model AINA (ja en format CTranslate2 natiu) ----
echo [PAS 5/5] Preparant model AINA...
echo    El model ja es distribueix en format CTranslate2.
echo    Nomes cal copiar els fitxers (si ja estan descarregats, triga uns segons).
echo    Si el model NO s'ha descarregat encara, pot trigar 10-20 min (~1.8 GB).
echo.
python C:\Users\santi\OneDrive\Documents\SLPL\taneu\descarrega_i_converteix.py
if errorlevel 1 (
    echo.
    echo ERROR durant la preparacio del model.
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
echo     Fes doble clic a: C:\Users\santi\OneDrive\Documents\SLPL\taneu\start_server_portatil.bat
echo.
echo   Per provar la traduccio (amb el servidor en marcha):
echo     python C:\Users\santi\OneDrive\Documents\SLPL\taneu\test_traduccio.py
echo =====================================================
echo.
pause
