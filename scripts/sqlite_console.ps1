param(
    [string]$Database = "events\test_uploads\app.db"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

if ([System.IO.Path]::IsPathRooted($Database)) {
    $DbPath = $Database
} else {
    $DbPath = Join-Path $ProjectRoot $Database
}

$Sqlite = (Get-Command sqlite3 -ErrorAction SilentlyContinue).Source
if (-not $Sqlite) {
    $Fallback = "C:\Tools\sqlite\sqlite3.exe"
    if (Test-Path $Fallback) {
        $Sqlite = $Fallback
    }
}

if (-not $Sqlite) {
    throw "sqlite3.exe was not found. Expected it on PATH or at C:\Tools\sqlite\sqlite3.exe."
}

if (-not (Test-Path $DbPath)) {
    Write-Host "Database does not exist yet. SQLite will create it:" -ForegroundColor Yellow
    Write-Host "  $DbPath" -ForegroundColor Yellow
}

Write-Host "Opening SQLite console:" -ForegroundColor Cyan
Write-Host "  $DbPath"
Write-Host ""
Write-Host "Useful commands: .tables  .schema TABLE_NAME  .headers on  .mode column  .quit" -ForegroundColor DarkGray
Write-Host ""

& $Sqlite $DbPath

