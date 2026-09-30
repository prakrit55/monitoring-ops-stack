#!/usr/bin/env python3
"""
Synthetic Prometheus RED and Kubernetes Metrics & Loki Logs Generator
Emits dynamic counters, histograms, gauges, and correlated structured logs matching the Service API Directory:
- ecommerce-ui
- product-catalog
- product-inventory
- shipping-and-handling
- order-management
- contact-support-team / contact-support
- service-a, service-b, service-c, service-d
"""

import os
import sys
import time
import math
import random
import uuid
import json
import threading
import urllib.request
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

START_TIME = time.time() - 3600  # Start 1 hour ago so counters have mature history
LOKI_URL = os.environ.get("LOKI_URL", "http://loki:3100/loki/api/v1/push")

SERVICES_DIRECTORY = [
    {
        "name": "ecommerce-ui",
        "aliases": ["ecommerce-ui"],
        "namespace": "production",
        "rps": 60,
        "err_ratio": 0.008,
        "p99": 0.06,
        "paths": [
            ("POST", "/api/signup"),
            ("POST", "/api/signin"),
            ("GET", "/api/profile"),
            ("GET", "/api/products"),
            ("GET", "/api/products/:id"),
            ("GET", "/api/inventory"),
            ("GET", "/api/inventory/:id"),
            ("GET", "/api/orders/:userId/cart"),
            ("POST", "/api/orders/:userId/cart"),
            ("GET", "/api/orders/:userId/cart/subtotal"),
            ("GET", "/api/orders/:userId/cart/shipping"),
            ("GET", "/api/orders/:userId/cart/total"),
            ("POST", "/api/orders/:userId/purchase"),
            ("GET", "/api/shipping-explanation"),
            ("GET", "/api/all-shipping-fees"),
            ("GET", "/api/contact-message"),
            ("POST", "/api/contact-submit"),
            ("GET", "/"),
        ]
    },
    {
        "name": "product-catalog",
        "aliases": ["product-catalog"],
        "namespace": "production",
        "rps": 45,
        "err_ratio": 0.003,
        "p99": 0.04,
        "paths": [
            ("GET", "/api/products"),
            ("GET", "/api/products/:id"),
            ("GET", "/metrics"),
        ]
    },
    {
        "name": "product-inventory",
        "aliases": ["product-inventory"],
        "namespace": "production",
        "rps": 30,
        "err_ratio": 0.005,
        "p99": 0.05,
        "paths": [
            ("GET", "/api/inventory"),
            ("GET", "/api/inventory/<int:product_id>"),
            ("POST", "/api/order/<int:product_id>"),
            ("GET", "/metrics"),
        ]
    },
    {
        "name": "shipping-and-handling",
        "aliases": ["shipping-and-handling"],
        "namespace": "production",
        "rps": 20,
        "err_ratio": 0.010,
        "p99": 0.08,
        "paths": [
            ("POST", "/shipping-fee"),
            ("GET", "/shipping-explanation"),
            ("GET", "/all-shipping-fees"),
            ("GET", "/metrics"),
        ]
    },
    {
        "name": "order-management",
        "aliases": ["order-management"],
        "namespace": "production",
        "rps": 25,
        "err_ratio": 0.012,
        "p99": 0.12,
        "paths": [
            ("GET", "/api/orders/{userId}/cart"),
            ("POST", "/api/orders/{userId}/cart"),
            ("GET", "/api/orders/{userId}/cart/subtotal"),
            ("GET", "/api/orders/{userId}/cart/shipping"),
            ("GET", "/api/orders/{userId}/cart/total"),
            ("POST", "/api/orders/{userId}/purchase"),
            ("GET", "/actuator/health"),
            ("GET", "/actuator/prometheus"),
        ]
    },
    {
        "name": "contact-support-team",
        "aliases": ["contact-support-team", "contact-support"],
        "namespace": "production",
        "rps": 15,
        "err_ratio": 0.006,
        "p99": 0.07,
        "paths": [
            ("GET", "/api/contact-message"),
            ("POST", "/api/contact-submit"),
            ("GET", "/metrics"),
        ]
    },
    {
        "name": "service-a",
        "aliases": ["service-a"],
        "namespace": "test",
        "rps": 40,
        "err_ratio": 0.005,
        "p99": 0.08,
        "paths": [
            ("POST", "/api/service-a/process"),
            ("GET", "/api/service-a/status"),
            ("POST", "/api/service-a/calculate"),
            ("GET", "/healthz"),
        ]
    },
    {
        "name": "service-b",
        "aliases": ["service-b"],
        "namespace": "test",
        "rps": 30,
        "err_ratio": 0.002,
        "p99": 0.05,
        "paths": [
            ("POST", "/api/service-b/auth"),
            ("GET", "/api/service-b/validate"),
            ("GET", "/api/service-b/token"),
            ("GET", "/healthz"),
        ]
    },
    {
        "name": "service-c",
        "aliases": ["service-c"],
        "namespace": "test",
        "rps": 20,
        "err_ratio": 0.015,
        "p99": 0.12,
        "paths": [
            ("POST", "/api/service-c/call-grpc"),
            ("GET", "/api/service-c/data"),
            ("GET", "/api/service-c/"),
            ("GET", "/healthz"),
        ]
    },
    {
        "name": "service-d",
        "aliases": ["service-d"],
        "namespace": "test",
        "rps": 15,
        "err_ratio": 0.045,
        "p99": 0.35,
        "paths": [
            ("POST", "/api/service-d/analyze"),
            ("GET", "/api/service-d/reports"),
            ("POST", "/api/service-d/export"),
            ("GET", "/healthz"),
        ]
    }
]

LE_BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
SIZE_BUCKETS = [128, 512, 1024, 4096, 16384, 65536, 262144, 1048576]

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/metrics"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.end_headers()
            
            now = time.time()
            elapsed = now - START_TIME
            lines = []
            
            lines.append("# HELP http_requests_total Total HTTP requests processed.")
            lines.append("# TYPE http_requests_total counter")
            
            lines.append("# HELP http_request_duration_seconds HTTP request duration histogram.")
            lines.append("# TYPE http_request_duration_seconds histogram")

            lines.append("# HELP http_response_size_bytes HTTP response size in bytes.")
            lines.append("# TYPE http_response_size_bytes histogram")
            
            lines.append("# HELP http_requests_in_flight Current in-flight requests.")
            lines.append("# TYPE http_requests_in_flight gauge")
            
            lines.append("# HELP kube_deployment_status_observed_generation Observed deployment generation.")
            lines.append("# TYPE kube_deployment_status_observed_generation gauge")
            
            lines.append("# HELP kube_pod_status_ready Pod ready condition.")
            lines.append("# TYPE kube_pod_status_ready gauge")
            
            lines.append("# HELP container_cpu_cfs_throttled_periods_total Container CPU throttled CFS periods.")
            lines.append("# TYPE container_cpu_cfs_throttled_periods_total counter")
            
            lines.append("# HELP container_cpu_cfs_periods_total Container CPU CFS periods.")
            lines.append("# TYPE container_cpu_cfs_periods_total counter")
            
            lines.append("# HELP container_memory_working_set_bytes Container memory working set.")
            lines.append("# TYPE container_memory_working_set_bytes gauge")
            
            lines.append("# HELP kube_pod_container_resource_limits Pod container resource limits.")
            lines.append("# TYPE kube_pod_container_resource_limits gauge")
            
            lines.append("# HELP node_vmstat_oom_kill Out-of-memory kill count.")
            lines.append("# TYPE node_vmstat_oom_kill counter")
            
            lines.append("# HELP node_vmstat_pgscan_kswapd Kernel swap daemon page scan rate.")
            lines.append("# TYPE node_vmstat_pgscan_kswapd counter")

            lines.append("# HELP node_uname_info Node system architecture information.")
            lines.append("# TYPE node_uname_info gauge")

            lines.append("# HELP service_exceptions_total Total service exceptions.")
            lines.append("# TYPE service_exceptions_total counter")

            lines.append("# HELP downstream_service_errors_total Total downstream service errors.")
            lines.append("# TYPE downstream_service_errors_total counter")

            # Node mock info
            lines.append('node_uname_info{instance="node-exporter:9100", machine="x86_64", nodename="k8s-worker-node-1", sysname="Linux"} 1')
            lines.append('node_vmstat_oom_kill{instance="node-exporter:9100"} 0')
            lines.append(f'node_vmstat_pgscan_kswapd{{instance="node-exporter:9100"}} {int(elapsed * 12)}')

            for s_idx, svc in enumerate(SERVICES_DIRECTORY):
                s_name = svc["name"]
                ns = svc["namespace"]
                base_rps = svc["rps"] + math.sin(elapsed / 60.0) * 3
                err_ratio = svc["err_ratio"]
                paths = svc["paths"]
                job_names = svc.get("aliases", [s_name])
                
                for j_name in job_names:
                    # Pod counts
                    for p_idx in [1, 2]:
                        pod_name = f"{j_name}-6f8b9d-{p_idx}"
                        lines.append(f'kube_pod_status_ready{{namespace="{ns}", pod="{pod_name}", condition="true"}} 1')
                        lines.append(f'container_cpu_cfs_throttled_periods_total{{namespace="{ns}", pod="{pod_name}", container="{j_name}"}} {int(elapsed * (5 + p_idx * 2))}')
                        lines.append(f'container_cpu_cfs_periods_total{{namespace="{ns}", pod="{pod_name}", container="{j_name}"}} {int(elapsed * 100)}')
                        
                        # Memory usage vs limits
                        mem_limit = 512 * 1024 * 1024  # 512 MiB
                        mem_used = int(mem_limit * (0.65 + 0.15 * math.sin(elapsed / 120.0 + p_idx)))
                        lines.append(f'kube_pod_container_resource_limits{{namespace="{ns}", pod="{pod_name}", container="{j_name}", resource="memory"}} {mem_limit}')
                        lines.append(f'container_memory_working_set_bytes{{namespace="{ns}", pod="{pod_name}", container="{j_name}"}} {mem_used}')

                    # Deployment rollout generation
                    gen = int(1 + (elapsed // 300))
                    lines.append(f'kube_deployment_status_observed_generation{{namespace="{ns}", deployment="{j_name}"}} {gen}')

                    # In-flight gauge
                    lines.append(f'http_requests_in_flight{{job="{j_name}", service="{j_name}", namespace="{ns}"}} {max(1, int(base_rps * 0.15))}')

                    # Downstream dependency error simulation
                    if j_name == "ecommerce-ui":
                        lines.append(f'downstream_service_errors_total{{job="{j_name}", target_service="product-catalog"}} {int(elapsed * 0.05)}')
                        lines.append(f'downstream_service_errors_total{{job="{j_name}", target_service="order-management"}} {int(elapsed * 0.08)}')
                        lines.append(f'downstream_service_errors_total{{job="{j_name}", target_service="shipping-and-handling"}} {int(elapsed * 0.02)}')

                    # Request counters & histograms per path
                    for method, path in paths:
                        path_weight = 1.0 + (abs(hash(path)) % 5) * 0.25
                        total_reqs = int(elapsed * (base_rps * path_weight / len(paths))) + 100
                        err_reqs = max(0, int(total_reqs * err_ratio))
                        client_err_reqs = max(0, int(total_reqs * 0.025))
                        redirect_reqs = max(0, int(total_reqs * 0.015))
                        
                        # Client aborts & timeouts under heavy load (HTTP 499 client closed request / HTTP 408 request timeout)
                        heavy_load_factor = max(0.003, 0.015 * (1.0 + math.sin(elapsed / 80.0 + s_idx)))
                        abort_499_reqs = max(0, int(total_reqs * heavy_load_factor * 0.7))
                        timeout_408_reqs = max(0, int(total_reqs * heavy_load_factor * 0.3))

                        success_reqs = max(0, total_reqs - err_reqs - client_err_reqs - redirect_reqs - abort_499_reqs - timeout_408_reqs)

                        # Status code distributions
                        lines.append(f'http_requests_total{{job="{j_name}", service="{j_name}", namespace="{ns}", status="200", status_code="200", method="{method}", path="{path}", route="{path}", endpoint="{path}"}} {success_reqs}')
                        lines.append(f'http_requests_total{{job="{j_name}", service="{j_name}", namespace="{ns}", status="302", status_code="302", method="{method}", path="{path}", route="{path}", endpoint="{path}"}} {redirect_reqs}')
                        lines.append(f'http_requests_total{{job="{j_name}", service="{j_name}", namespace="{ns}", status="404", status_code="404", method="{method}", path="{path}", route="{path}", endpoint="{path}"}} {client_err_reqs}')
                        lines.append(f'http_requests_total{{job="{j_name}", service="{j_name}", namespace="{ns}", status="408", status_code="408", method="{method}", path="{path}", route="{path}", endpoint="{path}"}} {timeout_408_reqs}')
                        lines.append(f'http_requests_total{{job="{j_name}", service="{j_name}", namespace="{ns}", status="499", status_code="499", method="{method}", path="{path}", route="{path}", endpoint="{path}"}} {abort_499_reqs}')
                        lines.append(f'http_requests_total{{job="{j_name}", service="{j_name}", namespace="{ns}", status="500", status_code="500", method="{method}", path="{path}", route="{path}", endpoint="{path}"}} {err_reqs}')

                        # Exceptions
                        if err_reqs > 0:
                            lines.append(f'service_exceptions_total{{job="{j_name}", exception_type="InternalServerError", endpoint="{path}"}} {err_reqs}')
                        if abort_499_reqs > 0:
                            lines.append(f'service_exceptions_total{{job="{j_name}", exception_type="ClientClosedRequest", endpoint="{path}"}} {abort_499_reqs}')
                        if timeout_408_reqs > 0:
                            lines.append(f'service_exceptions_total{{job="{j_name}", exception_type="RequestTimeout", endpoint="{path}"}} {timeout_408_reqs}')

                        # Latency histogram distribution
                        sum_duration = total_reqs * (svc["p99"] * 0.4)
                        for le in LE_BUCKETS:
                            fraction = min(1.0, 1.0 - math.exp(-le / (svc["p99"] * 0.3)))
                            bucket_count = int(total_reqs * fraction)
                            lines.append(f'http_request_duration_seconds_bucket{{job="{j_name}", service="{j_name}", namespace="{ns}", method="{method}", path="{path}", route="{path}", endpoint="{path}", le="{le}"}} {bucket_count}')
                        lines.append(f'http_request_duration_seconds_bucket{{job="{j_name}", service="{j_name}", namespace="{ns}", method="{method}", path="{path}", route="{path}", endpoint="{path}", le="+Inf"}} {total_reqs}')
                        lines.append(f'http_request_duration_seconds_sum{{job="{j_name}", service="{j_name}", namespace="{ns}", method="{method}", path="{path}", route="{path}", endpoint="{path}"}} {sum_duration:.4f}')
                        lines.append(f'http_request_duration_seconds_count{{job="{j_name}", service="{j_name}", namespace="{ns}", method="{method}", path="{path}", route="{path}", endpoint="{path}"}} {total_reqs}')

                        # Payload size distribution
                        avg_payload = 2048 * path_weight
                        lines.append(f'http_response_size_bytes_sum{{job="{j_name}", service="{j_name}", method="{method}", path="{path}", route="{path}", endpoint="{path}"}} {int(total_reqs * avg_payload)}')
                        lines.append(f'http_response_size_bytes_count{{job="{j_name}", service="{j_name}", method="{method}", path="{path}", route="{path}", endpoint="{path}"}} {total_reqs}')
                        for sb in SIZE_BUCKETS:
                            frac = min(1.0, sb / (avg_payload * 3.0))
                            lines.append(f'http_response_size_bytes_bucket{{job="{j_name}", service="{j_name}", method="{method}", path="{path}", route="{path}", endpoint="{path}", le="{sb}"}} {int(total_reqs * frac)}')
                        lines.append(f'http_response_size_bytes_bucket{{job="{j_name}", service="{j_name}", method="{method}", path="{path}", route="{path}", endpoint="{path}", le="+Inf"}} {total_reqs}')

            payload = "\n".join(lines) + "\n"
            self.wfile.write(payload.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        now_str = time.strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{now_str}] {self.client_address[0]} - {format % args}", flush=True)


def push_logs_to_loki(loki_payload):
    """Attempt pushing batched streams to Loki HTTP push API."""
    try:
        req = urllib.request.Request(
            LOKI_URL,
            data=json.dumps(loki_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            pass
    except Exception:
        # Loki may be unreachable or initializing; silently fallback to stdout
        pass


def run_mock_log_generator():
    """
    Continuously generates realistic structured JSON logs synchronized with Prometheus metrics.
    Pushes directly to Loki and prints to stdout for Docker/Fluent-Bit log harvesting.
    """
    time.sleep(2)  # Short warmup
    
    ERROR_MESSAGES = {
        "ecommerce-ui": [
            ("DatabaseConnectionTimeout", "Connection pool exhausted to Mongo cluster during product aggregation", "MongoTimeoutException at ConnectionPool.acquire (pool.js:88)"),
            ("UpstreamService503", "Upstream order-management returned HTTP 503 Service Unavailable", "HttpGatewayError at OrderClient.submit (orderClient.js:42)"),
            ("RedisCacheError", "Redis connection reset while fetching user session cache", "RedisCommandTimeout at RedisClient.get (redis.js:19)"),
        ],
        "product-catalog": [
            ("MongoQueryError", "Mongo execution error: cursor exceeded maximum time limit 500ms", "MongoExecutionTimeout at Cursor.toArray (mongo.js:105)"),
            ("SerializationError", "Failed to serialize JSON response payload for category listing", "TypeError at JSON.stringify (<anonymous>)"),
        ],
        "product-inventory": [
            ("DeadlockDetected", "PostgreSQL transaction deadlock detected while updating stock lock", "PSQLException: ERROR: deadlock detected (inventory.py:77)"),
            ("InventoryShortage", "Requested quantity exceeds available physical SKU stock", "InsufficientStockError: item_id=8831 qty=4 (stock.py:31)"),
        ],
        "shipping-and-handling": [
            ("CarrierAPIError", "FedEx / UPS carrier rates API returned HTTP 500 Internal Error", "CarrierGatewayException at ShippingService.calculateRate (Shipping.java:120)"),
            ("RateEngineTimeout", "Distance calculation matrix timed out after 3000ms", "TimeoutException at MatrixResolver.resolve (Matrix.java:45)"),
        ],
        "order-management": [
            ("PaymentGatewayException", "Stripe payment capture failed with status: processor_declined", "PaymentError at StripeClient.charge (PaymentGateway.java:94)"),
            ("KafkaProduceError", "Kafka broker timed out acknowledging order-created event", "KafkaTimeoutException at OrderProducer.send (OrderProducer.java:62)"),
        ],
        "contact-support-team": [
            ("SMTPSendFailed", "SMTP server rejected relay for ticket confirmation email", "SMTPServerDisconnected: Connection unexpectedly closed (mail.py:54)"),
        ],
        "service-a": [("WorkerTimeout", "Service-A calculate worker exceeded deadline", "WorkerTimeout: task id 0x8821")],
        "service-b": [("TokenValidationFailed", "Service-B RSA signature verification failed", "JWTValidationError: Key expired")],
        "service-c": [("GrpcUnavailable", "Service-C gRPC upstream channel entered TRANSIENT_FAILURE", "StatusRuntimeException: UNAVAILABLE")],
        "service-d": [("ReportGenerationError", "Service-D memory limit reached during report aggregation", "OOMKilled simulation")],
    }

    while True:
        try:
            now_sec = time.time()
            now_nano = int(now_sec * 1e9)
            now_iso = datetime.now(timezone.utc).isoformat()
            elapsed = now_sec - START_TIME

            streams = []

            for s_idx, svc in enumerate(SERVICES_DIRECTORY):
                s_name = svc["name"]
                ns = svc["namespace"]
                paths = svc["paths"]
                err_ratio = svc["err_ratio"]
                p99 = svc["p99"]
                
                # Pick 1-2 random endpoint requests per tick
                sample_count = random.randint(1, 2)
                for _ in range(sample_count):
                    method, path = random.choice(paths)
                    trace_id = uuid.uuid4().hex[:16]
                    span_id = uuid.uuid4().hex[:16]
                    
                    # Determine response code based on error distribution
                    roll = random.random()
                    heavy_load_roll = math.sin(elapsed / 80.0 + s_idx)
                    
                    if roll < err_ratio:
                        status = 500
                        level = "error"
                        duration_ms = round(random.uniform(p99 * 1.5, p99 * 5.0) * 1000, 2)
                        err_choice = random.choice(ERROR_MESSAGES.get(s_name, [("ServerError", "Internal server error occurred", "Stack trace")]))
                        log_body = {
                            "timestamp": now_iso,
                            "level": level,
                            "job": s_name,
                            "service": s_name,
                            "namespace": ns,
                            "environment": "production",
                            "method": method,
                            "path": path,
                            "route": path,
                            "status": status,
                            "duration_ms": duration_ms,
                            "trace_id": trace_id,
                            "span_id": span_id,
                            "error_type": err_choice[0],
                            "message": f"HTTP {method} {path} failed [500]: {err_choice[1]}",
                            "stack_trace": err_choice[2]
                        }
                    elif heavy_load_roll > 0.7 and roll < (err_ratio + 0.04):
                        status = 499
                        level = "warn"
                        duration_ms = round(random.uniform(2500.0, 4500.0), 2)
                        log_body = {
                            "timestamp": now_iso,
                            "level": level,
                            "job": s_name,
                            "service": s_name,
                            "namespace": ns,
                            "environment": "production",
                            "method": method,
                            "path": path,
                            "route": path,
                            "status": status,
                            "duration_ms": duration_ms,
                            "trace_id": trace_id,
                            "span_id": span_id,
                            "error_type": "ClientClosedRequest",
                            "message": f"HTTP {method} {path} cancelled: Upstream proxy/client aborted connection under heavy load (HTTP 499)"
                        }
                    elif heavy_load_roll > 0.8 and roll < (err_ratio + 0.06):
                        status = 408
                        level = "warn"
                        duration_ms = 5000.0
                        log_body = {
                            "timestamp": now_iso,
                            "level": level,
                            "job": s_name,
                            "service": s_name,
                            "namespace": ns,
                            "environment": "production",
                            "method": method,
                            "path": path,
                            "route": path,
                            "status": status,
                            "duration_ms": duration_ms,
                            "trace_id": trace_id,
                            "span_id": span_id,
                            "error_type": "RequestTimeout",
                            "message": f"HTTP {method} {path} timed out waiting for request payload after {duration_ms}ms (HTTP 408)"
                        }
                    elif roll < (err_ratio + 0.05):
                        status = 404
                        level = "warn"
                        duration_ms = round(random.uniform(5.0, 20.0), 2)
                        log_body = {
                            "timestamp": now_iso,
                            "level": level,
                            "job": s_name,
                            "service": s_name,
                            "namespace": ns,
                            "environment": "production",
                            "method": method,
                            "path": path,
                            "route": path,
                            "status": status,
                            "duration_ms": duration_ms,
                            "trace_id": trace_id,
                            "span_id": span_id,
                            "message": f"HTTP {method} {path} resource not found (HTTP 404)"
                        }
                    elif roll < (err_ratio + 0.07):
                        status = 302
                        level = "info"
                        duration_ms = round(random.uniform(4.0, 15.0), 2)
                        log_body = {
                            "timestamp": now_iso,
                            "level": level,
                            "job": s_name,
                            "service": s_name,
                            "namespace": ns,
                            "environment": "production",
                            "method": method,
                            "path": path,
                            "route": path,
                            "status": status,
                            "duration_ms": duration_ms,
                            "trace_id": trace_id,
                            "span_id": span_id,
                            "message": f"HTTP {method} {path} redirecting to login session [302 Found]"
                        }
                    else:
                        status = 200
                        level = "info"
                        duration_ms = round(max(2.0, random.gauss(p99 * 250, p99 * 50)), 2)
                        log_body = {
                            "timestamp": now_iso,
                            "level": level,
                            "job": s_name,
                            "service": s_name,
                            "namespace": ns,
                            "environment": "production",
                            "method": method,
                            "path": path,
                            "route": path,
                            "status": status,
                            "duration_ms": duration_ms,
                            "trace_id": trace_id,
                            "span_id": span_id,
                            "message": f"HTTP {method} {path} handled successfully [200 OK] in {duration_ms}ms"
                        }

                    log_json_str = json.dumps(log_body)
                    
                    # Print to stdout with flushing so Docker captures it
                    print(log_json_str, flush=True)

                    # Loki stream format
                    streams.append({
                        "stream": {
                            "job": s_name,
                            "service": s_name,
                            "namespace": ns,
                            "environment": "production",
                            "level": level
                        },
                        "values": [
                            [str(now_nano), log_json_str]
                        ]
                    })
                    now_nano += 1000000  # Offset timestamps slightly

            if streams:
                push_logs_to_loki({"streams": streams})

            time.sleep(1.0)
        except Exception:
            time.sleep(1.0)


if __name__ == "__main__":
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

    total_services = len(SERVICES_DIRECTORY)
    total_endpoints = sum(len(s["paths"]) for s in SERVICES_DIRECTORY)
    print("=" * 60, flush=True)
    print("Synthetic RED & K8s Metrics + Loki Logs Generator Started", flush=True)
    print(f"Listening on: http://0.0.0.0:8080/metrics", flush=True)
    print(f"Loki Push Target: {LOKI_URL}", flush=True)
    print(f"Registered Services: {total_services}", flush=True)
    print(f"Total Service Endpoints: {total_endpoints}", flush=True)
    print("=" * 60, flush=True)

    # Start background correlated log generator thread
    log_thread = threading.Thread(target=run_mock_log_generator, daemon=True)
    log_thread.start()

    # Serve Prometheus metric scrapes
    server = HTTPServer(("0.0.0.0", 8080), MetricsHandler)
    server.serve_forever()
