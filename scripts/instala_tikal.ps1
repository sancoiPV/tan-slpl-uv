# instala_tikal.ps1
# Descarrega i instal·la Okapi Framework Tikal al directori tools/tikal/
#
# Us: powershell -ExecutionPolicy Bypass -File scripts\instala_tikal.ps1
#
# Servei de Llengues i Politica Linguistica - Universitat de Valencia

$TIKAL_VERSION = "1.47.0"
$TIKAL_URL = "https://okapiframework.org/binaries/main/$TIKAL_VERSION/okapi-apps_win-x86_64_$TIKAL_VERSION.zip"

# Directori d'installacio: taneu/tools/tikal/
$SCRIPT_DIR  = Split-Path -Parent $MyInvocation.MyCommand.Definition
$PROJECT_DIR = Split-Path -Parent $SCRIPT_DIR
$TIKAL_DIR   = Join-Path $PROJECT_DIR "tools\tikal"
$TIKAL_ZIP   = Join-Path $TIKAL_DIR "tikal-$TIKAL_VERSION.zip"
$TIKAL_CMD   = Join-Path $TIKAL_DIR "tikal.cmd"

Write-Host ""
Write-Host "==================================================="
Write-Host "  Installacio d'Okapi Framework Tikal $TIKAL_VERSION"
Write-Host "  Servei de Llengues - Universitat de Valencia"
Write-Host "==================================================="
Write-Host ""

# Comprova si ja esta installat
if (Test-Path $TIKAL_CMD) {
    Write-Host "Tikal ja installat a: $TIKAL_DIR"
    Write-Host "  Executable: $TIKAL_CMD"
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

# Busca tikal.cmd dins l'estructura descomprimida
$tikal_found = Get-ChildItem -Path $TIKAL_DIR -Recurse -Filter "tikal.cmd" | Select-Object -First 1
if ($tikal_found) {
    if ($tikal_found.FullName -ne $TIKAL_CMD) {
        # Mou el contingut al directori arrel de tools/tikal/
        $source_dir = $tikal_found.DirectoryName
        Write-Host "  Movent fitxers de $source_dir a $TIKAL_DIR..."
        Get-ChildItem -Path $source_dir | Move-Item -Destination $TIKAL_DIR -Force -ErrorAction SilentlyContinue
        Remove-Item $source_dir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# Verificacio final
Write-Host ""
if (Test-Path $TIKAL_CMD) {
    Write-Host "==================================================="
    Write-Host "  Tikal installat correctament!"
    Write-Host ""
    Write-Host "  Executable: $TIKAL_CMD"
    Write-Host ""
    Write-Host '  Per usar el pipeline XLIFF:'
    Write-Host '  .venv\Scripts\python scripts\corpus_builder_xliff.py `'
    Write-Host '      --input "corpus d''entrenament i afinament" `'
    Write-Host '      --output "corpus d''entrenament i afinament\processed" `'
    Write-Host '      --tikal tools\tikal\tikal.cmd `'
    Write-Host '      --min-similitud 0.10'
    Write-Host "==================================================="
} else {
    Write-Host "  tikal.cmd no trobat a $TIKAL_DIR"
    Write-Host "  Contingut del directori:"
    Get-ChildItem $TIKAL_DIR | ForEach-Object { Write-Host "    $_" }
    Write-Host ""
    Write-Host "  Potser l'estructura interna del ZIP ha canviat."
    Write-Host "  Comprova manualment i ajusta TIKAL_CMD al script Python."
    exit 1
}
