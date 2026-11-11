$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "Created .env from .env.example for local Compose. Do not commit it."
}

docker compose up --build -d

$deadline = (Get-Date).AddMinutes(4)
do {
  Start-Sleep -Seconds 5
  $inspect = docker inspect --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}" (docker compose ps -q api) 2>$null
  Write-Host "api health: $inspect"
  if ($inspect -eq "healthy") { break }
} while ((Get-Date) -lt $deadline)

$apiPort = "8000"
Get-Content ".env" | ForEach-Object {
  if ($_ -match '^\s*HOST_API_PORT\s*=\s*(.+)\s*$') { $apiPort = $Matches[1].Trim() }
}
$health = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$apiPort/health"
$ready = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$apiPort/ready"
if ($health.StatusCode -ne 200) { throw "/health failed: $($health.StatusCode) $($health.Content)" }
if ($ready.StatusCode -ne 200) { throw "/ready failed: $($ready.StatusCode) $($ready.Content)" }
Write-Host "health: $($health.Content)"
Write-Host "ready: $($ready.Content)"
docker compose ps
Write-Host "Local deployment verified."
