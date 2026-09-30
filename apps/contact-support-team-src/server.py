import os
import psycopg2
import time
import shutil
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import prometheus_client
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)
CORS(app)

# Prometheus Resource Usage Metrics (Disk, CPU Load, System)
SYSTEM_DISK_USAGE_BYTES = Gauge(
    'system_disk_usage_bytes',
    'System disk space usage in bytes',
    ['path', 'type']
)

SYSTEM_CPU_LOAD_1M = Gauge(
    'system_cpu_load_average_1m',
    'System CPU load average for 1 minute'
)

# Prometheus Metrics Configuration
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    'http_request_duration_seconds',
    'Duration of HTTP requests in seconds (response time & latency)',
    ['method', 'route', 'status_code'],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

HTTP_RESPONSE_TIME_MILLISECONDS = Histogram(
    'http_response_time_milliseconds',
    'Total time taken to process a request and generate a response in milliseconds',
    ['method', 'route', 'status_code'],
    buckets=[5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000]
)

HTTP_REQUESTS_TOTAL = Counter(
    'http_requests_total',
    'Total number of HTTP requests processed (Request Volume & Throughput)',
    ['method', 'route', 'status_code']
)

# Total HTTP Error Requests Counter (Error Rate Tracking)
HTTP_REQUESTS_ERRORS_TOTAL = Counter(
    'http_requests_errors_total',
    'Total number of HTTP requests resulting in client (4xx) or server (5xx) errors',
    ['method', 'route', 'status_code', 'error_type']
)

# Service Exceptions & Operational Failures Counter
SERVICE_EXCEPTIONS_TOTAL = Counter(
    'service_exceptions_total',
    'Total number of internal exceptions and operational failures encountered',
    ['exception_type', 'endpoint']
)

# Throughput: In-Flight Active Requests Gauge (Concurrency / Current Load)
HTTP_REQUESTS_IN_FLIGHT = Gauge(
    'http_requests_in_flight',
    'Current number of simultaneous active HTTP requests being processed (concurrency/load)',
    ['route', 'method']
)

# Throughput: Response Payload Size in Bytes (Network throughput)
HTTP_RESPONSE_SIZE_BYTES = Histogram(
    'http_response_size_bytes',
    'Size of HTTP response payload in bytes (network throughput & bandwidth tracking)',
    ['method', 'route', 'status_code'],
    buckets=[100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000]
)

def get_route():
    if request.url_rule and request.url_rule.rule:
        return request.url_rule.rule
    return 'unmatched'

@app.before_request
def before_request():
    if request.path != '/metrics':
        route = get_route()
        HTTP_REQUESTS_IN_FLIGHT.labels(route=route, method=request.method).inc()
        request._in_flight_tracked = (route, request.method)
    request.start_time = time.time()

@app.teardown_request
def teardown_request(exception=None):
    if hasattr(request, '_in_flight_tracked'):
        route, method = request._in_flight_tracked
        HTTP_REQUESTS_IN_FLIGHT.labels(route=route, method=method).dec()

@app.after_request
def after_request(response):
    if request.path != '/metrics':
        resp_time_sec = time.time() - getattr(request, 'start_time', time.time())
        resp_time_ms = resp_time_sec * 1000.0
        route = get_route()
        status = str(response.status_code)

        HTTP_REQUEST_DURATION_SECONDS.labels(
            method=request.method,
            route=route,
            status_code=status
        ).observe(resp_time_sec)

        HTTP_RESPONSE_TIME_MILLISECONDS.labels(
            method=request.method,
            route=route,
            status_code=status
        ).observe(resp_time_ms)

        HTTP_REQUESTS_TOTAL.labels(
            method=request.method,
            route=route,
            status_code=status
        ).inc()

        # Track Error Rate (4xx and 5xx)
        if response.status_code >= 400:
            error_type = 'server_error' if response.status_code >= 500 else 'client_error'
            HTTP_REQUESTS_ERRORS_TOTAL.labels(
                method=request.method,
                route=route,
                status_code=status,
                error_type=error_type
            ).inc()

        # Track Response Payload Size (Network Throughput)
        if response.content_length:
            HTTP_RESPONSE_SIZE_BYTES.labels(
                method=request.method,
                route=route,
                status_code=status
            ).observe(response.content_length)

    return response

@app.route('/metrics', methods=['GET'])
def metrics():
    # Update system disk metrics
    try:
        total, used, free = shutil.disk_usage('/')
        SYSTEM_DISK_USAGE_BYTES.labels(path='/', type='total').set(total)
        SYSTEM_DISK_USAGE_BYTES.labels(path='/', type='used').set(used)
        SYSTEM_DISK_USAGE_BYTES.labels(path='/', type='free').set(free)
    except Exception:
        pass

    # Update system load average
    try:
        load = os.getloadavg()
        SYSTEM_CPU_LOAD_1M.set(load[0])
    except Exception:
        pass

    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

# Load database config from environment variables (with defaults)
DB_HOST = os.environ.get('POSTGRES_HOST', 'localhost')
DB_PORT = os.environ.get('POSTGRES_PORT', '5432')
DB_NAME = os.environ.get('POSTGRES_DB', 'postgres')
DB_USER = os.environ.get('POSTGRES_USER', 'postgres')
DB_PASS = os.environ.get('POSTGRES_PASSWORD', 'postgres')

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )

def init_db():
    retries = 15
    while retries > 0:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS contact_submissions (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    subject VARCHAR(255),
                    message TEXT NOT NULL,
                    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            cursor.close()
            conn.close()
            print("Contact support database initialized successfully.")
            return
        except Exception as e:
            retries -= 1
            print(f"Failed to initialize contact support database (retries left: {retries}): {e}")
            if retries == 0:
                print("Could not connect to database after all retries. Starting server anyway.")
            else:
                time.sleep(3)

# Initialize DB on startup
init_db()

@app.route('/api/contact-message', methods=['GET'])
def get_contact_message():
    response = {
        'message': "We're here to help! If you have any questions, concerns, or feedback, please don't hesitate to reach out to us. Our dedicated support team is ready to assist you."
    }
    return jsonify(response)

@app.route('/api/contact-submit', methods=['POST'])
def submit_contact_form():
    try:
        post_data = request.get_json()
        print("Received submission:", post_data)
        
        name = post_data.get('name', '')
        email = post_data.get('email', '')
        subject = post_data.get('subject', '')
        message = post_data.get('message', '')

        if not name or not email or not message:
            return jsonify({'error': 'Name, email, and message are required'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO contact_submissions (name, email, subject, message)
            VALUES (%s, %s, %s, %s)
        ''', (name, email, subject, message))
        conn.commit()
        cursor.close()
        conn.close()

        response = {'status': 'success', 'message': 'Your message has been successfully submitted.'}
        return jsonify(response)
    except Exception as e:
        print("Error submitting contact form:", e)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)