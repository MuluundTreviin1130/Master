# PowerShell Script zum Setup der LCA-Datenbank
# Bitte Python-Pfad anpassen, falls notwendig

# Setze das Repo-Root als Arbeitsverzeichnis
$RepoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
Set-Location $RepoRoot

Write-Host "Repo-Root: $RepoRoot" -ForegroundColor Cyan
Write-Host ""

# Python-Pfad (aus dem Projekt-venv)
# Wichtig: Pfad mit Leerzeichen muss in Anführungszeichen stehen
$Python = 'C:\Users\Philipp Thunshirn\Desktop\PhD\Python model\V2H_energy_community_surrogat_datafile_structured\.venv\Scripts\python.exe'

# Prüfe, ob Python gefunden werden kann
Write-Host "Teste Python-Pfad..." -ForegroundColor Yellow
try {
    $PythonVersion = & $Python --version 2>&1
    Write-Host "✓ Python gefunden: $PythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Python nicht gefunden unter: $Python" -ForegroundColor Red
    Write-Host "Bitte passe den Python-Pfad in diesem Script an." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Führe LCA-Setup-Schritte aus..." -ForegroundColor Cyan
Write-Host "=" * 70

# Schritt 1: Bootstrap Project
Write-Host ""
Write-Host "[1/4] Bootstrap Project..." -ForegroundColor Yellow
& $Python "V2H_energy_community_surrogat_datafilenew\datafile_Umstellung\Data\LCA_data\scripts\01_bootstrap_project.py" --project "my_lca_project"
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Fehler bei Schritt 1" -ForegroundColor Red
    exit $LASTEXITCODE
}
Write-Host "✓ Schritt 1 abgeschlossen" -ForegroundColor Green

# Schritt 2: Install LCIA Methods
Write-Host ""
Write-Host "[2/4] Install LCIA Methods..." -ForegroundColor Yellow
& $Python "V2H_energy_community_surrogat_datafilenew\datafile_Umstellung\Data\LCA_data\scripts\02_install_lcia_methods_patched.py" --project "my_lca_project" --ensure_biosphere3
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Fehler bei Schritt 2" -ForegroundColor Red
    exit $LASTEXITCODE
}
Write-Host "✓ Schritt 2 abgeschlossen" -ForegroundColor Green

# Schritt 3: Import Ecoinvent
Write-Host ""
Write-Host "[3/4] Import Ecoinvent..." -ForegroundColor Yellow
$EcoinventPath = "C:\Users\Philipp Thunshirn\Desktop\PhD\openLCA\ecoinvent 3.11_cutoff_ecoSpold02"
Write-Host "Ecoinvent-Pfad: $EcoinventPath" -ForegroundColor Cyan

if (-not (Test-Path $EcoinventPath)) {
    Write-Host "✗ Ecoinvent-Pfad nicht gefunden: $EcoinventPath" -ForegroundColor Red
    Write-Host "Bitte passe den Pfad in diesem Script an." -ForegroundColor Red
    exit 1
}

& $Python "V2H_energy_community_surrogat_datafilenew\datafile_Umstellung\Data\LCA_data\scripts\04_import_ecoinvent.py" --project "my_lca_project" --db "ecoinvent 3.11 cutoff" --ecospold $EcoinventPath
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Fehler bei Schritt 3" -ForegroundColor Red
    exit $LASTEXITCODE
}
Write-Host "✓ Schritt 3 abgeschlossen" -ForegroundColor Green

# Schritt 4: Check Environment
Write-Host ""
Write-Host "[4/4] Check Environment..." -ForegroundColor Yellow
& $Python "V2H_energy_community_surrogat_datafilenew\datafile_Umstellung\Data\LCA_data\scripts\00_check_environment.py" --project "my_lca_project"
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Fehler bei Schritt 4" -ForegroundColor Red
    exit $LASTEXITCODE
}
Write-Host "✓ Schritt 4 abgeschlossen" -ForegroundColor Green

Write-Host ""
Write-Host "=" * 70
Write-Host "✅ Alle LCA-Setup-Schritte erfolgreich abgeschlossen!" -ForegroundColor Green
