import os
import time
import grpc
from flask import Flask, request, jsonify

# Import generated protobuf classes
import service_pb2
import service_pb2_grpc

# OpenTelemetry Metrics Setup
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource

otel_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
request_counter = None
request_duration = None

if otel_endpoint:
    print(f"Initializing OTLP metric exporter to {otel_endpoint}")
    # Normalize endpoint
    endpoint_url = otel_endpoint if otel_endpoint.startswith("http") else f"http://{otel_endpoint}"
    if not endpoint_url.endswith("/v1/metrics"):
        endpoint_url = f"{endpoint_url}/v1/metrics"
        
    exporter = OTLPMetricExporter(endpoint=endpoint_url)
    resource = Resource.create({"service.name": "service-d"})
    reader = PeriodicExportingMetricReader(exporter, export_interval_millis=15000)
    provider = MeterProvider(metric_readers=[reader], resource=resource)
    metrics.set_meter_provider(provider)
    
    meter = metrics.get_meter("service-d")
    request_counter = meter.create_counter(
        "http_requests_total",
        description="Total number of HTTP requests received",
        unit="1"
    )
    request_duration = meter.create_histogram(
        "http_request_duration_seconds",
        description="Duration of HTTP requests in seconds",
        unit="s"
    )

app = Flask(__name__)

service_a_url = os.environ.get("SERVICE_A_GRPC_URL", "localhost:50051")
service_b_url = os.environ.get("SERVICE_B_GRPC_URL", "localhost:50052")

@app.before_request
def handle_options_and_timer():
    request.start_time = time.time()
    if request.method == 'OPTIONS':
        response = jsonify({})
        response.status_code = 200
        return response

@app.after_request
def record_metrics(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-Correlation-Id'

    if request.method != 'OPTIONS' and request_counter and hasattr(request, "start_time"):
        duration = time.time() - request.start_time
        route = request.url_rule.rule if request.url_rule else request.path
        
        labels = {
            "http.method": request.method,
            "http.route": route,
            "http.status_code": str(response.status_code)
        }
        request_counter.add(1, labels)
        request_duration.record(duration, labels)
    return response

@app.route("/")
def index():
    return jsonify({"status": "up", "service": "service-d"})

@app.route("/call-grpc")
def call_grpc():
    name = request.args.get("name", "Python Client")
    print(f"Received request to /call-grpc, calling Service A via gRPC at {service_a_url}")
    
    try:
        # Create gRPC channel to Service A
        with grpc.insecure_channel(service_a_url) as channel:
            stub = service_pb2_grpc.ServiceAStub(channel)
            # Call Service A with timeout
            response_a = stub.CallServiceA(
                service_pb2.ServiceARequest(name=name),
                timeout=5.0
            )
            
            print(f"Received gRPC response from Service A: {response_a.message}")
            return jsonify({
                "message": "Hello from Service D (Python)!",
                "grpc_response_from_a": {
                    "message": response_a.message,
                    "correlation_id": response_a.correlation_id,
                    "service_b_response": response_a.service_b_response
                }
            })
    except grpc.RpcError as e:
        print(f"gRPC Call failed: {e}")
        return jsonify({"error": f"gRPC call failed: {e.details() if hasattr(e, 'details') else str(e)}"}), 502

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8083))
    app.run(host="0.0.0.0", port=port)
