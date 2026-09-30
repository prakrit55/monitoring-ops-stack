# Tier 2: Fine-Grained Route Drilldown Dashboard Specification

## 1. Executive Summary & Dashboard Objective

The **Tier 2: Fine-Grained Route Drilldown Dashboard** (`tier2-route-drilldown.json`) is designed for SREs, DevOps engineers, and application developers to investigate fine-grained route-level latency distributions, error dynamics, concurrency saturation, downstream dependency cascades, and network throughput across the microservice stack.

It complements the hierarchical observability stack:
- **Tier 1 (`/d/tier1-executive`)**: Executive & NOC Overview (Platform Availability, Global Ingress RPS, Cluster Saturation).
- **Tier 2 RED (`/d/tier2-red-service`)**: Service-level Health tracking aggregate Rate, Errors, and Duration.
- **Tier 2 Route Drilldown (`/d/tier2-route-drilldown`)**: Per-endpoint and parameterized URI drilldown resolving microsecond latency spikes, client aborts, thread starvation, and upstream error propagation.
- **Tier 3 USE (`/d/tier3-use-infra`)**: Node and container resource utilization, saturation, and hardware errors (CFS throttling, Memory Working Set, OOM Kills).

---

## 2. Microservice Application Inventory & Endpoint Mapping

The dashboard monitors and harmonizes metrics from all microservices in the `apps/` directory:

| Microservice | Language / Framework | Default Port | Registered Endpoints & HTTP Methods | Downstream Call Graph / Datastore |
| :--- | :--- | :--- | :--- | :--- |
| **`ecommerce-ui`** | Node.js / Express + Vite React | `3000` | • `POST /api/signup`<br>• `POST /api/signin`<br>• `GET /api/profile`<br>• `GET /api/products`<br>• `GET /api/products/:id`<br>• `GET /api/inventory`<br>• `GET /api/inventory/:id`<br>• `GET /api/orders/:userId/cart`<br>• `POST /api/orders/:userId/cart`<br>• `GET /api/orders/:userId/cart/subtotal`<br>• `GET /api/orders/:userId/cart/shipping`<br>• `GET /api/orders/:userId/cart/total`<br>• `POST /api/orders/:userId/purchase`<br>• `GET /api/shipping-explanation`<br>• `GET /api/all-shipping-fees`<br>• `GET /api/contact-message`<br>• `POST /api/contact-submit`<br>• `GET /`<br>• `GET /metrics` | Calls `product-catalog`, `product-inventory`, `order-management`, `shipping-and-handling`, `contact-support-team` |
| **`product-catalog`** | Node.js / Express | `3001` | • `GET /api/products`<br>• `GET /api/products/:id`<br>• `GET /metrics` | MongoDB (Port 27017), Redis Cache (Port 6379) |
| **`product-inventory`** | Python / Flask | `3002` | • `GET /api/inventory`<br>• `GET /api/inventory/<int:product_id>`<br>• `POST /api/order/<int:product_id>`<br>• `GET /metrics` | PostgreSQL (`inventory` table) |
| **`shipping-and-handling`** | Go / net/http | `3003` | • `POST /shipping-fee`<br>• `GET /shipping-explanation`<br>• `GET /all-shipping-fees`<br>• `GET /metrics` | SQLite (`shipping.db`) |
| **`order-management`** | Java / Spring Boot + Micrometer | `9090` | • `GET /api/orders/{userId}/cart`<br>• `POST /api/orders/{userId}/cart`<br>• `GET /api/orders/{userId}/cart/subtotal`<br>• `GET /api/orders/{userId}/cart/shipping`<br>• `GET /api/orders/{userId}/cart/total`<br>• `POST /api/orders/{userId}/purchase`<br>• `GET /actuator/health`<br>• `GET /actuator/prometheus` | Calls `product-catalog`, `product-inventory`, `shipping-and-handling` |
| **`contact-support-team`** | Python / Flask | `3004` | • `GET /api/contact-message`<br>• `POST /api/contact-submit`<br>• `GET /metrics` | PostgreSQL (`contacts` table) |
| **`mock-metrics`** | Python Synthetic Generator | `8080` | • `POST /api/v1/checkout`<br>• `GET /api/v1/cart`<br>• `GET /api/v1/inventory`<br>• `POST /api/v1/payment`<br>• `GET /healthz`<br>• `GET /metrics` | Synthetic microservices (`service-a`, `service-b`, `service-c`, `service-d`) |

---

## 3. Metric Schema & Multi-Framework Harmonization Strategy

Different microservices emit metrics using distinct naming conventions and label keys. The dashboard uses PromQL label alignment to coalesce all metrics into unified dimensions:

```
+------------------------------------+-----------------------------+------------------------------------+
| Framework / Service Source         | Label Convention Emitted    | Harmonized PromQL Target Label     |
+------------------------------------+-----------------------------+------------------------------------+
| Node.js, Python, Go                | route="/api/products"       | route                              |
| Python Flask (dynamic params)      | route="/api/inventory/<id>" | route                              |
| Synthetic Traffic Generator        | path="/api/v1/checkout"     | label_replace(..., "route", ...)   |
| Spring Boot / Micrometer           | uri="/api/orders/{id}/cart" | label_replace(..., "route", ...)   |
| Status Codes (Node, Python, Go)    | status_code="500"           | status_code                        |
| Status Codes (Spring Boot)         | status="500"                | label_replace(..., "status_code")  |
| Service Scope                      | job vs service              | job=~"$service" / service=~"$service"|
+------------------------------------+-----------------------------+------------------------------------+
```

---

## 4. Dashboard Structure & Panel Specifications

### Section 0: Service API Directory & Active Endpoint Catalog (`$service`)

1. **Service API Contracts & Route Registry** (Text / Markdown Panel):
   - Interactive specification card detailing runtime tech stack, exposed ports, route templates, and downstream dependencies for the selected `$service`.
2. **Discovered Live Endpoints for `$service`** (Table Panel):
   - Queries live Prometheus series grouped by `(route, method)`.
   - Metrics: **Endpoint URI / Route**, **HTTP Method**, **Ingress RPS** (sparkline), **P95 Latency** (threshold gradient), **5xx Error Rate (%)** (gradient background), and **In-Flight Concurrency**.

---

### Section 1: Quick KPI Summary & Instant Route Health

- **Selected Route RPS** (`stat`): Real-time request throughput across selected route filters.
- **P95 Route Latency** (`stat`): 95th percentile latency (Green: $\le 250\text{ms}$, Yellow: $250\text{-}500\text{ms}$, Red: $>500\text{ms}$).
- **P99 Tail Latency** (`stat`): Worst 1% user latency SLA (Green: $\le 500\text{ms}$, Red: $>1000\text{ms}$).
- **5xx Error Rate (%)** (`stat`): Proportion of 5xx internal server errors (Green: $<0.1\%$, Yellow: $0.1\text{-}1.0\%$, Red: $>1.0\%$).
- **Active In-Flight Sockets** (`stat`): Real-time gauge of open concurrent HTTP worker sockets.

---

### Section 2: Row 1 - High-Throughput Triage & Outlier Identification

- **Top Degraded Routes Under Load** (`table`):
   - Multi-metric sorted table ranking all routes by 5xx Error Rate % and P99 Latency.
   - Includes columns for Ingress RPS, P50 Median, P95 Tail, and In-Flight concurrency load.
- **Throughput Distribution (Top Endpoints)** (`bargauge`):
   - Horizontal gradient bar gauge displaying the top 10 busiest endpoints by RPS.
- **HTTP Status Code Ratio** (`piechart`):
   - Donut chart visualizing response distributions across 2xx (Success), 3xx (Redirect), 4xx (Client Error), and 5xx (Server Error).

---

### Section 3: Row 2 - Deep Latency Profiling & Micro-SLA Breakdown

- **Latency Heatmap (Concurrency & Thread Stalls)** (`heatmap`):
   - Multi-bucket logarithmic histogram visualization using `Spectral` palette. Detects multimodal distributions, thread lock stalls, and GC pauses.
- **Latency Percentile Spread (P50, P90, P95, P99)** (`timeseries`):
   - Percentile curves with horizontal SLA threshold lines at $300\text{ms}$ (Warning) and $1.0\text{s}$ (Critical). P99 is emphasized with a bold $3\text{px}$ stroke.
- **Mean vs Median vs P99 Tail Latency Skew** (`timeseries`):
   - Compares arithmetic mean duration `rate(sum)/rate(count)` with P50 and P99. A diverging mean indicates that isolated outlier requests are disproportionately dragging system resources.

---

### Section 4: Row 3 - High-Throughput Constraints & System Saturation

- **In-Flight Concurrency per Route** (`timeseries`, stacked area):
   - Tracks active worker thread allocation per endpoint. High in-flight count with stable RPS indicates downstream database lock contention or socket pool depletion.
- **Client Aborts & Drops (499 / Broken Pipes)** (`timeseries`):
   - Tracks HTTP 499 / 408 client dropoffs caused by premature user navigation or reverse-proxy timeouts.
- **Payload Size Distribution (Egress Bandwidth Bottlenecks)** (`timeseries`):
   - Tracks P95 response size in bytes via `http_response_size_bytes` histogram to detect jumbo response payloads saturating network interfaces.

---

### Section 5: Row 4 - Error Decomposition & Downstream Cascades

- **Error Breakdown by Route & HTTP Status** (`timeseries`, stacked bars):
   - Categorizes client-side errors (400, 401, 403, 404, 429) vs server-side failures (500, 502, 503, 504).
- **Service Operational Exceptions & Failures** (`timeseries`):
   - Visualizes `service_exceptions_total` rates labeled by `exception_type`, `endpoint`, and `operation`.
- **Gateway Downstream Dependency Cascades** (`timeseries`):
   - Monitors `downstream_service_errors_total` on UI gateway/orchestrator calls to pinpoint cascading microservice failures.

---

## 5. Templating Variables

| Variable Name | Type | Query / Definition | Functionality |
| :--- | :--- | :--- | :--- |
| **`DS_PROMETHEUS`** | `datasource` | `prometheus` | Datasource selector. |
| **`environment`** | `custom` | `production, staging, local` | Environment filter. |
| **`namespace`** | `query` | `label_values(http_requests_total, namespace)` | Kubernetes namespace scoping. |
| **`service`** | `query` | `label_values(http_requests_total, job)` | Microservice filter (supports `ecommerce-ui`, `product-catalog`, `product-inventory`, `order-management`, `shipping-and-handling`, `contact-support-team`, `mock-metrics`). |
| **`method`** | `query` | `label_values(http_requests_total, method)` | HTTP Method selector (`GET`, `POST`, `PUT`, `DELETE`, `PATCH`, `All`). |
| **`route`** | `query` | `label_values(http_requests_total, path)` | Dynamic endpoint filter automatically populated for the active `$service`. |

---

## 6. SRE Troubleshooting & SLA Reference

| Metric Signal | Healthy Baseline | Warning Threshold | Critical SLA Breach | Diagnostic Action |
| :--- | :--- | :--- | :--- | :--- |
| **5xx Error Rate** | $< 0.05\%$ | $\ge 0.10\%$ | $\ge 1.00\%$ | Check `Service Operational Exceptions` & `Gateway Cascades` to isolate downstream failure source. |
| **P95 Latency** | $< 100\text{ms}$ | $\ge 250\text{ms}$ | $\ge 500\text{ms}$ | Inspect `Latency Heatmap` for bi-modal distribution; check database query latencies. |
| **P99 Tail Latency** | $< 250\text{ms}$ | $\ge 500\text{ms}$ | $\ge 1000\text{ms}$ | Inspect `Mean vs Median Skew` and `In-Flight Concurrency` for thread pool starvation. |
| **Client Aborts (499)** | $0\text{ req/s}$ | $\ge 0.5\text{ req/s}$ | $\ge 2.0\text{ req/s}$ | Client timeout is shorter than backend processing time; scale workers or optimize queries. |
| **In-Flight Concurrency** | $< 15\text{ sockets}$ | $\ge 25\text{ sockets}$ | $\ge 100\text{ sockets}$ | Indicates downstream blocking I/O, slow lock release, or connection pool exhaustion. |
