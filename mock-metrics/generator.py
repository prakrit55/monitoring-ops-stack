#!/usr/bin/env python3
"""
Synthetic Prometheus RED and Kubernetes Metrics Generator
Emits dynamic counters, histograms, and gauges matching the full Service API Directory:
- ecommerce-ui
- product-catalog
- product-inventory
- shipping-and-handling
- order-management
- contact-support-team / contact-support
- service-a, service-b, service-c, service-d
"""

import time
import math
import random
from http.server import HTTPServer, BaseHTTPRequestHandler

START_TIME = time.time()

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

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/metrics"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.end_headers()
            
            elapsed = time.time() - START_TIME
            lines = []
            
            lines.append("# HELP http_requests_total Total HTTP requests processed.")
            lines.append("# TYPE http_requests_total counter")
            
            lines.append("# HELP http_request_duration_seconds HTTP request duration histogram.")
            lines.append("# TYPE http_request_duration_seconds histogram")
            
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

            # Node mock info
            lines.append('node_uname_info{instance="node-exporter:9100", machine="x86_64", nodename="k8s-worker-node-1", sysname="Linux"} 1')
            lines.append('node_vmstat_oom_kill{instance="node-exporter:9100"} 0')
            lines.append(f'node_vmstat_pgscan_kswapd{{instance="node-exporter:9100"}} {int(elapsed * 12)}')

            for svc in SERVICES_DIRECTORY:
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

                    # Request counters & histograms per path
                    for method, path in paths:
                        # Individual variance per endpoint
                        path_weight = 1.0 + (hash(path) % 5) * 0.2
                        total_reqs = int(elapsed * (base_rps * path_weight / len(paths))) + 1
                        err_reqs = max(0, int(total_reqs * err_ratio))
                        client_err_reqs = max(0, int(total_reqs * 0.02))
                        success_reqs = max(0, total_reqs - err_reqs - client_err_reqs)

                        # Emit path, route, and endpoint for universal compatibility across all PromQL styles
                        lines.append(f'http_requests_total{{job="{j_name}", service="{j_name}", namespace="{ns}", status="200", status_code="200", method="{method}", path="{path}", route="{path}", endpoint="{path}"}} {success_reqs}')
                        lines.append(f'http_requests_total{{job="{j_name}", service="{j_name}", namespace="{ns}", status="404", status_code="404", method="{method}", path="{path}", route="{path}", endpoint="{path}"}} {client_err_reqs}')
                        lines.append(f'http_requests_total{{job="{j_name}", service="{j_name}", namespace="{ns}", status="500", status_code="500", method="{method}", path="{path}", route="{path}", endpoint="{path}"}} {err_reqs}')

                        # Latency histogram distribution
                        sum_duration = total_reqs * (svc["p99"] * 0.4)
                        for le in LE_BUCKETS:
                            fraction = min(1.0, 1.0 - math.exp(-le / (svc["p99"] * 0.3)))
                            bucket_count = int(total_reqs * fraction)
                            lines.append(f'http_request_duration_seconds_bucket{{job="{j_name}", service="{j_name}", namespace="{ns}", method="{method}", path="{path}", route="{path}", endpoint="{path}", le="{le}"}} {bucket_count}')
                        lines.append(f'http_request_duration_seconds_bucket{{job="{j_name}", service="{j_name}", namespace="{ns}", method="{method}", path="{path}", route="{path}", endpoint="{path}", le="+Inf"}} {total_reqs}')
                        lines.append(f'http_request_duration_seconds_sum{{job="{j_name}", service="{j_name}", namespace="{ns}", method="{method}", path="{path}", route="{path}", endpoint="{path}"}} {sum_duration:.4f}')
                        lines.append(f'http_request_duration_seconds_count{{job="{j_name}", service="{j_name}", namespace="{ns}", method="{method}", path="{path}", route="{path}", endpoint="{path}"}} {total_reqs}')

            payload = "\n".join(lines) + "\n"
            self.wfile.write(payload.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8080), MetricsHandler)
    print("Synthetic RED & K8s Metrics Generator running with full Service API Directory on port 8080...")
    server.serve_forever()
