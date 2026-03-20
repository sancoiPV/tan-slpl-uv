# instala_tikal.ps1
# Descarrega i instal·la Okapi Framework Tikal al directori tools/tikal/
#
# Us: powershell -ExecutionPolicy Bypass -File scripts\instala_tikal.ps1
#
# Servei de Llengues i Politica Linguistica - Universitat de Valencia

$TIKAL_VERSION = "1.47.0"

# CANVI 1: URL correcta amb nom de fitxer win32-x86_64
$TIKAL_URL = "https://okapiframework.org/binaries/main/1.47.0/okapi-apps_win32-x86_64_1.47.0.zip"

# Directori d'installacio: taneu/tools/tikal/
$SCRIPT_DIR  = Split-Path -Parent $MyInvocation.MyCommand.Definition
$PROJECT_DIR = Split-Path -Parent $SCRIPT_DIR
$TIKAL_DIR   = Join-Path $PROJECT_DIR "tools\tikal"

# CANVI 2: nom del ZIP alineat amb el nom real del fitxer descarregat
$TIKAL_ZIP = "$TIKAL_DIR\okapi-apps_win32-x86_64_1.47.0.zip"

# Ruta esperada per a la comprovacio "ja installat" (pot estar en subcarpeta)
$TIKAL_CMD_EXPECTED = Join-Path $TIKAL_DIR "tikal.cmd"

Write-Host ""
Write-Host "==================================================="
Write-Host "  Installacio d'Okapi Framework Tikal $TIKAL_VERSION"
Write-Host "  Servei de Llengues - Universitat de Valencia"
Write-Host "==================================================="
Write-Host ""

# Comprova si ja esta installat (cerca recursiva)
$tikal_existent = Get-ChildItem -Path $TIKAL_DIR -Recurse -Filter "tikal.cmd" -ErrorAction SilentlyContinue |
                  Select-Object -First 1 -ExpandProperty FullName
if ($tikal_existent) {
    Write-Host "Tikal ja installat a: $tikal_existent"
    Write-Host ""
    exit 0
}

# Comprova Java
Write-Host "Comprovant Java..."
try {
    $java_version = & java -version 2>&1
    Write-Host "  Java disponible: $($java_version[0])"
} catch {
    Write-Host "  ERROR: Java no trobat al PATH."
    Write-Host "    Installa Java 11+ des de: https://adoptium.net/"
    exit 1
}

# Crea el directori d'installacio
Write-Host ""
Write-Host "Creant directori: $TIKAL_DIR"
New-Item -ItemType Directory -Force -Path $TIKAL_DIR | Out-Null

# Descarrega
Write-Host ""
Write-Host "Descarregant Tikal $TIKAL_VERSION..."
Write-Host "  URL: $TIKAL_URL"
Write-Host "  Desti: $TIKAL_ZIP"
try {
    $progressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $TIKAL_URL -OutFile $TIKAL_ZIP -UseBasicParsing
    Write-Host "  Descarrega completada"
} catch {
    Write-Host "  ERROR en la descarrega: $($_.Exception.Message)"
    Write-Host ""
    Write-Host "  Si falla la descarrega automatica, descarrega manualment des de:"
    Write-Host "  https://okapiframework.org/wiki/index.php/Tikal"
    Write-Host "  i descomprimeix a: $TIKAL_DIR"
    exit 1
}

# Descomprimeix
Write-Host ""
Write-Host "Descomprimint..."
try {
    Expand-Archive -Path $TIKAL_ZIP -DestinationPath $TIKAL_DIR -Force
    Write-Host "  Descomprimit correctament"
} catch {
    Write-Host "  ERROR en la descompressio: $($_.Exception.Message)"
    exit 1
}

# Elimina el ZIP per estalviar espai
Remove-Item $TIKAL_ZIP -Force -ErrorAction SilentlyContinue

# CANVI 3: Cerca tikal.cmd recursivament dins del directori d'installacio
$TIKAL_CMD = Get-ChildItem -Path $TIKAL_DIR -Recurse -Filter "tikal.cmd" |
             Select-Object -First 1 -ExpandProperty FullName

if ($TIKAL_CMD) {
    Write-Host "  tikal.cmd trobat a: $TIKAL_CMD"
} else {
    Write-Host "  ERROR: tikal.cmd no trobat a $TIKAL_DIR"
    Write-Host "  Comprova que el ZIP s'ha descomprimit correctament."
    exit 1
}

# CANVI 4: Missatge final amb la ruta real de tikal.cmd
Write-Host ""
Write-Host "Tikal installat correctament."
Write-Host "  Executable: $TIKAL_CMD"
Write-Host ""
Write-Host "Ara pots executar el pipeline XLIFF:"
Write-Host '  .venv\Scripts\python scripts\corpus_builder_xliff.py `'
Write-Host '      --input "corpus d''entrenament i afinament" `'
Write-Host '      --output "corpus d''entrenament i afinament\processed" `'
Write-Host "      --tikal `"$TIKAL_CMD`""
