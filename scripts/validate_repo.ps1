Write-Host "--- Running Consolidated Validation ---" -ForegroundColor Cyan

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "--- Running pytest ---" -ForegroundColor Yellow
python -m pytest tests/ -v
if ($LASTEXITCODE -ne 0) {
    Write-Host "Tests failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "--- Running self-audit ---" -ForegroundColor Yellow
python scripts/audit.py --dir .
if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 1) {
    Write-Host "Audit script failed to execute." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "`nValidation complete!" -ForegroundColor Green
exit 0
