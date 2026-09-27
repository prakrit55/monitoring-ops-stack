#!/usr/bin/env python3
"""
Synthetic Prometheus RED and Kubernetes Metrics Generator
Emits dynamic counters, histograms, and gauges for local observability validation.
"""

import time
import math
import random
from http.server import HTTPServer, BaseHTTPRequestHandler

START_TIME = time.time()

SERVICES = [
    {"name": "service-a", "namespace": "test", "rps": 45, "err_ratio": 0.005, "p99": 0.08},
    {"name": "service-b", "namespace": "test", "rps": 30, "err_ratio": 0.002, "p99": 0.05},
    {"name": "service-c", "namespace": "test", "rps": 20, "err_ratio": 0.015, "p99": 0.12},
    {"name": "service-d", "namespace": "test", "rps": 15, "err_ratio": 0.045, "p99": 0.35},
]

PATHS = [
    ("/api/v1/checkout", "POST"),
    ("/api/v1/cart", "GET"),
    ("/api/v1/inventory", "GET"),
    ("/api/v1/payment", "POST"),
    ("/healthz", "GET"),
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
            lines.append('node_uname_info{instance="mock-metrics:8080", machine="x86_64", nodename="k8s-worker-node-2", sysname="Linux"} 1')
            lines.append('node_vmstat_oom_kill{instance="node-exporter:9100"} 0')
            lines.append(f'node_vmstat_pgscan_kswapd{{instance="node-exporter:9100"}} {int(elapsed * 12)}')

            for svc in SERVICES:
                s_name = svc["name"]
                ns = svc["namespace"]
                base_rps = svc["rps"] + math.sin(elapsed / 60.0) * 5
                err_ratio = svc["err_ratio"]
                
                # Pod counts
                for p_idx in [1, 2]:
                    pod_name = f"{s_name}-6f8b9d-{p_idx}"
                    lines.append(f'kube_pod_status_ready{{namespace="{ns}", pod="{pod_name}", condition="true"}} 1')
                    lines.append(f'container_cpu_cfs_throttled_periods_total{{namespace="{ns}", pod="{pod_name}", container="{s_name}"}} {int(elapsed * (5 + p_idx * 2))}')
                    lines.append(f'container_cpu_cfs_periods_total{{namespace="{ns}", pod="{pod_name}", container="{s_name}"}} {int(elapsed * 100)}')
                    
                    # Memory usage vs limits
                    mem_limit = 512 * 1024 * 1024  # 512 MiB
                    mem_used = int(mem_limit * (0.65 + 0.15 * math.sin(elapsed / 120.0 + p_idx)))
                    lines.append(f'kube_pod_container_resource_limits{{namespace="{ns}", pod="{pod_name}", container="{s_name}", resource="memory"}} {mem_limit}')
                    lines.append(f'container_memory_working_set_bytes{{namespace="{ns}", pod="{pod_name}", container="{s_name}"}} {mem_used}')

                # Deployment rollout generation (changes occasionally)
                gen = int(1 + (elapsed // 300))
                lines.append(f'kube_deployment_status_observed_generation{{namespace="{ns}", deployment="{s_name}"}} {gen}')

                # Request counters & histograms per path
                for path, method in PATHS:
                    total_reqs = int(elapsed * (base_rps / len(PATHS)))
                    err_reqs = int(total_reqs * err_ratio)
                    client_err_reqs = int(total_reqs * 0.02)
                    success_reqs = max(0, total_reqs - err_reqs - client_err_reqs)

                    # 200 Success
                    lines.append(f'http_requests_total{{job="{s_name}", service="{s_name}", namespace="{ns}", status="200", status_code="200", method="{method}", path="{path}"}} {success_reqs}')
                    # 404 Client Error
                    lines.append(f'http_requests_total{{job="{s_name}", service="{s_name}", namespace="{ns}", status="404", status_code="404", method="{method}", path="{path}"}} {client_err_reqs}')
                    # 500 Server Error
                    lines.append(f'http_requests_total{{job="{s_name}", service="{s_name}", namespace="{ns}", status="500", status_code="500", method="{method}", path="{path}"}} {err_reqs}')

                    # Latency histogram distribution
                    sum_duration = total_reqs * (svc["p99"] * 0.4)
                    cumulative = 0
                    for le in LE_BUCKETS:
                        fraction = min(1.0, 1.0 - math.exp(-le / (svc["p99"] * 0.3)))
                        bucket_count = int(total_reqs * fraction)
                        lines.append(f'http_request_duration_seconds_bucket{{job="{s_name}", service="{s_name}", namespace="{ns}", method="{method}", path="{path}", le="{le}"}} {bucket_count}')
                    lines.append(f'http_request_duration_seconds_bucket{{job="{s_name}", service="{s_name}", namespace="{ns}", method="{method}", path="{path}", le="+Inf"}} {total_reqs}')
                    lines.append(f'http_request_duration_seconds_sum{{job="{s_name}", service="{s_name}", namespace="{ns}", method="{method}", path="{path}"}} {sum_duration:.4f}')
                    lines.append(f'http_request_duration_seconds_count{{job="{s_name}", service="{s_name}", namespace="{ns}", method="{method}", path="{path}"}} {total_reqs}')

            payload = "\n".join(lines) + "\n"
            self.wfile.write(payload.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Quiet logging

if __name__ == "__main__":
    print("Starting Synthetic Metrics Server on :8080...")
    server = HTTPServer(("0.0.0.0", 8080), MetricsHandler)
    server.serve_forever()
