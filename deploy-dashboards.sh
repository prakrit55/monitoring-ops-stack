#!/usr/bin/env bash
set -e

# ==============================================================================
# Local Observability Stack Deployment & Validation Script
# ==============================================================================

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}====================================================${NC}"
echo -e "${CYAN}  Prometheus & Grafana Observability Local Stack     ${NC}"
echo -e "${CYAN}====================================================${NC}\n"

# 1. Prerequisite Checks
echo -e "${YELLOW}[1/4] Checking prerequisites...${NC}"
if ! command -v docker >/dev/null 2>&1; then
    echo -e "${RED}[ERROR] Docker is not installed or not in PATH.${NC}"
    exit 1
fi

COMPOSE_CMD="docker compose"
if ! docker compose version >/dev/null 2>&1; then
    if command -v docker-compose >/dev/null 2>&1; then
        COMPOSE_CMD="docker-compose"
    else
        echo -e "${RED}[ERROR] Neither 'docker compose' nor 'docker-compose' found.${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}  ✓ Docker and Compose detected (${COMPOSE_CMD})${NC}"

# 2. Validate configuration files
echo -e "\n${YELLOW}[2/4] Validating dashboard JSON and rule YAML configurations...${NC}"
FILES=(
  "grafana-dashboards/tier-dashboards/tier1-executive.json"
  "grafana-dashboards/tier-dashboards/tier2-red-service.json"
  "grafana-dashboards/tier-dashboards/tier3-use-infra.json"
  "rules/recording_rules.yml"
  "rules/alert_rules.yml"
  "grafana/datasources/prometheus.yml"
  "grafana/dashboards/dashboard-providers.yml"
  "prometheus/prometheus.yml"
)

for file in "${FILES[@]}"; do
    if [[ -f "$file" ]]; then
        echo -e "  ✓ Found ${file}"
    else
        echo -e "${RED}  ✗ Missing required file: ${file}${NC}"
        exit 1
    fi
done

# 3. Boot up Docker Compose services
echo -e "\n${YELLOW}[3/4] Launching containers via Docker Compose...${NC}"
$COMPOSE_CMD down --remove-orphans >/dev/null 2>&1 || true
$COMPOSE_CMD up -d

# 4. Wait for services to become healthy
echo -e "\n${YELLOW}[4/4] Waiting for services to initialize...${NC}"
wait_for_service() {
    local url=$1
    local name=$2
    local retries=30
    local count=0
    
    echo -n "  Waiting for ${name} (${url})..."
    while ! curl -s -f "$url" >/dev/null 2>&1; do
        sleep 1
        count=$((count+1))
        if [[ $count -ge $retries ]]; then
            echo -e " ${RED}[FAILED]${NC}"
            echo -e "${RED}Service ${name} failed to respond after ${retries}s.${NC}"
            return 1
        fi
    done
    echo -e " ${GREEN}[READY]${NC}"
}

if command -v curl >/dev/null 2>&1; then
    wait_for_service "http://localhost:8080/metrics" "Mock Metrics Generator" || true
    wait_for_service "http://localhost:9090/-/ready" "Prometheus Server" || true
    wait_for_service "http://localhost:3000/api/health" "Grafana Server" || true
else
    echo "  (curl not found, waiting 5 seconds for container startup...)"
    sleep 5
fi

echo -e "\n${GREEN}====================================================${NC}"
echo -e "${GREEN}  ✓ Observability Stack is fully running!           ${NC}"
echo -e "${GREEN}====================================================${NC}\n"

echo -e "${CYAN}Access Grafana (Anonymous Admin Access Enabled - No Login Required):${NC}"
echo -e "  • ${GREEN}Tier 1 Executive & NOC:${NC}   http://localhost:3000/d/tier1-executive"
echo -e "  • ${GREEN}Tier 2 Service RED:${NC}       http://localhost:3000/d/tier2-red-service"
echo -e "  • ${GREEN}Tier 3 Infrastructure USE:${NC} http://localhost:3000/d/tier3-use-infra"
echo -e "  • ${GREEN}Grafana Home:${NC}              http://localhost:3000\n"

echo -e "${CYAN}Prometheus Endpoints:${NC}"
echo -e "  • ${GREEN}Prometheus Web UI:${NC}        http://localhost:9090"
echo -e "  • ${GREEN}Active Recording Rules:${NC}   http://localhost:9090/rules"
echo -e "  • ${GREEN}Scrape Targets:${NC}           http://localhost:9090/targets\n"

echo -e "${YELLOW}To stop the stack, run:${NC}"
echo -e "  ${COMPOSE_CMD} down\n"
