# Brightway-Suche mit Projekt-venv ausführen
# Nutzung: .\run_search.ps1 --query "electrolysis" --location AT
$RepoRoot = (Get-Item $PSScriptRoot).Parent.Parent.Parent.Parent.FullName
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Script = Join-Path $PSScriptRoot "brightway_search.py"

if (-not (Test-Path $Python)) {
    Write-Host "Fehler: .venv nicht gefunden. Installiere zuerst: pip install -r Data\LCA_data\requirements-lca.txt" -ForegroundColor Red
    exit 1
}

$defaultArgs = @("--project", "my_lca_project", "--db", "ecoinvent 3.11 cutoff")
& $Python $Script @defaultArgs @args
