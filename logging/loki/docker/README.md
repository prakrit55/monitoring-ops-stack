# Docker Compose - Full Observability & Logging Stack (Loki + Prometheus)

This directory contains configuration files and a [`docker-compose.yml`](file:///R:/Devops%20territory/monitoring-ops-stack/logging/loki/docker-compose.yml) stack directly mirroring the tools, Helm charts, and dashboards defined in [`kustomization.yaml`](file:///R:/Devops%20territory/monitoring-ops-stack/logging/loki/kustomization.yaml).

---

## 📦 Services Included

| Service | Image / Tool | Port(s) | Role & Description |
|---|---|---|---|
| **Loki** | `grafana/loki:3.0.0` | `3100` | High-performance log aggregation engine with local TSDB & filesystem storage |
| **Fluent Bit** | `fluent/fluent-bit:3.0.4` | `2020`, `24224` | High-throughput log processor & shipper forwarding container & synthetic logs to Loki |
| **Prometheus** | `prom/prometheus:v2.51.2` | `9090` | Metrics engine configured with Tier 1/2/3 recording rules, alert rules, and scraping all components |
| **Alertmanager** | `prom/alertmanager:v0.27.0` | `9093` | Alert routing dispatcher with critical (PagerDuty) and warning (Slack) channel trees |
| **Grafana** | `grafana/grafana:10.4.2` | `3000` | UI with pre-provisioned Loki & Prometheus datasources and all 15 Kubernetes & Tier dashboards |
| **Node Exporter** | `prom/node-exporter:v1.7.0` | `9100` | Host hardware & OS metric collector (CPU, memory, disk, network) |
| **Mock Metrics** | `python:3.11-alpine` | `8080` | Live synthetic traffic generator providing real-time RED microservice & Kubernetes metrics |

---

## 🚀 Quick Start

Navigate to the Loki folder:

```bash
cd "logging/loki"
```

Start the entire observability stack:

```bash
docker compose up -d
```

Check running services:

```bash
docker compose ps
```

View aggregated logs:

```bash
docker compose logs -f
```

Stop the stack:

```bash
docker compose down
```

---

## 🌐 Endpoints & Web UIs

- **Grafana Dashboard UI**: [http://localhost:3000](http://localhost:3000)
  - **Credentials**: `admin` / `admin` (or anonymous admin access)
  - **Datasources**: Pre-configured for both **Prometheus** and **Loki**
  - **Dashboards**:
    - 📁 **Observability Tiers**:
      - `Tier 1: Executive & Platform SLOs`
      - `Tier 2: RED Microservice Observability`
      - `Tier 3: USE Host & Infrastructure`
    - 📁 **Kubernetes Monitoring**:
      - 12 comprehensive Kubernetes cluster, pod, and node monitoring dashboards
- **Prometheus UI**: [http://localhost:9090](http://localhost:9090) (Status > Rules, Status > Targets)
- **Alertmanager UI**: [http://localhost:9093](http://localhost:9093)
- **Loki API / Readiness**: [http://localhost:3100/ready](http://localhost:3100/ready)
- **Fluent Bit Prometheus Metrics**: [http://localhost:2020/api/v1/metrics/prometheus](http://localhost:2020/api/v1/metrics/prometheus)
- **Synthetic Microservice Metrics**: [http://localhost:8080/metrics](http://localhost:8080/metrics)
- **Node Exporter**: [http://localhost:9100/metrics](http://localhost:9100/metrics)

---

## 🧪 Testing & Verifying Logs & Metrics

1. **Verify Log Flow in Grafana**:
   - Open [http://localhost:3000/explore](http://localhost:3000/explore)
   - Select datasource **Loki**
   - Run query: `{job="fluent-bit"}` or `{service="fluent-bit-demo"}`
2. **Verify Alert Rules in Prometheus**:
   - Open [http://localhost:9090/alerts](http://localhost:9090/alerts) to inspect live evaluations for Tier 1 SLOs, Tier 2 RED, and Tier 3 USE alert conditions.
