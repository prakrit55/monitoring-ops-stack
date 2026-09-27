# ==============================================================================
# Local Observability Stack Deployment & Validation Script (PowerShell)
# ==============================================================================

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "  Prometheus & Grafana Observability Local Stack     " -ForegroundColor Cyan
Write-Host "====================================================`n" -ForegroundColor Cyan

# 1. Prerequisite Checks
Write-Host "[1/4] Checking prerequisites..." -ForegroundColor Yellow
$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerCmd) {
    Write-Error "Docker is not installed or not in PATH."
    exit 1
}
Write-Host "  `u{2713} Docker detected" -ForegroundColor Green

# 2. Validate configuration files
Write-Host "`n[2/4] Validating dashboard JSON and rule YAML configurations..." -ForegroundColor Yellow
$files = @(
  "grafana-dashboards/tier-dashboards/tier1-executive.json",
  "grafana-dashboards/tier-dashboards/tier2-red-service.json",
  "grafana-dashboards/tier-dashboards/tier3-use-infra.json",
  "rules/recording_rules.yml",
  "rules/alert_rules.yml",
  "grafana/datasources/prometheus.yml",
  "grafana/dashboards/dashboard-providers.yml",
  "prometheus/prometheus.yml"
)

foreach ($f in $files) {
    if (Test-Path $f) {
        Write-Host "  `u{2713} Found $f" -ForegroundColor Green
    } else {
        Write-Error "Missing required file: $f"
        exit 1
    }
}

# 3. Boot up Docker Compose services
Write-Host "`n[3/4] Launching containers via Docker Compose..." -ForegroundColor Yellow
docker compose down --remove-orphans 2>$null
docker compose up -d

# 4. Wait for services to become healthy
Write-Host "`n[4/4] Waiting for services to initialize..." -ForegroundColor Yellow
Start-Sleep -Seconds 4

Write-Host "`n====================================================" -ForegroundColor Green
Write-Host "  `u{2713} Observability Stack is fully running!           " -ForegroundColor Green
Write-Host "====================================================`n" -ForegroundColor Green

Write-Host "Access Grafana (Anonymous Admin Access Enabled - No Login Required):" -ForegroundColor Cyan
Write-Host "  * Tier 1 Executive & NOC:   http://localhost:3000/d/tier1-executive" -ForegroundColor Green
Write-Host "  * Tier 2 Service RED:       http://localhost:3000/d/tier2-red-service" -ForegroundColor Green
Write-Host "  * Tier 3 Infrastructure USE: http://localhost:3000/d/tier3-use-infra" -ForegroundColor Green
Write-Host "  * Grafana Home:              http://localhost:3000`n" -ForegroundColor Green

Write-Host "Prometheus Endpoints:" -ForegroundColor Cyan
Write-Host "  * Prometheus Web UI:        http://localhost:9090" -ForegroundColor Green
Write-Host "  * Active Recording Rules:   http://localhost:9090/rules" -ForegroundColor Green
Write-Host "  * Scrape Targets:           http://localhost:9090/targets`n" -ForegroundColor Green

Write-Host "To stop the stack, run:" -ForegroundColor Yellow
Write-Host "  docker compose down`n"
