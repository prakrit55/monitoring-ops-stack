import os
import psycopg2
import time
import shutil
from psycopg2.extras import RealDictCursor
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

# Default inventory to seed if database is new/empty
default_inventory = [
    {'id': 1, 'quantity': 100},
    {'id': 2, 'quantity': 50},
    {'id': 3, 'quantity': 75},
    {'id': 4, 'quantity': 120},
    {'id': 5, 'quantity': 30},
    {'id': 6, 'quantity': 60},
    {'id': 7, 'quantity': 40},
    {'id': 8, 'quantity': 90},
    {'id': 9, 'quantity': 80},
    {'id': 10, 'quantity': 70},
    {'id': 11, 'quantity': 20},
    {'id': 12, 'quantity': 55}
]

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
                CREATE TABLE IF NOT EXISTS inventory (
                    id INTEGER PRIMARY KEY,
                    quantity INTEGER NOT NULL
                )
            ''')
            conn.commit()
            
            # Check if empty
            cursor.execute('SELECT COUNT(*) FROM inventory')
            count = cursor.fetchone()[0]
            if count == 0:
                for item in default_inventory:
                    cursor.execute('INSERT INTO inventory (id, quantity) VALUES (%s, %s)', (item['id'], item['quantity']))
                conn.commit()
            cursor.close()
            conn.close()
            print("Database initialized successfully.")
            return
        except Exception as e:
            retries -= 1
            print(f"Failed to initialize database (retries left: {retries}): {e}")
            if retries == 0:
                print("Could not connect to database after all retries. Starting server anyway.")
            else:
                time.sleep(3)

# Initialize DB on startup
init_db()

# Get inventory for all products
@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('SELECT id, quantity FROM inventory')
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(list(rows))
    except Exception as e:
        print("Error fetching inventory:", e)
        return jsonify({'error': str(e)}), 500

# Get inventory for a single product by ID
@app.route('/api/inventory/<int:product_id>', methods=['GET'])
def get_product_inventory(product_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('SELECT id, quantity FROM inventory WHERE id = %s', (product_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if row:
            return jsonify(dict(row))
        else:
            return jsonify({'error': 'Product not found'}), 404
    except Exception as e:
        print("Error fetching product inventory:", e)
        return jsonify({'error': str(e)}), 500

# Reduce the quantity of a product by 1
@app.route('/api/order/<int:product_id>', methods=['POST'])
def order_product(product_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('SELECT id, quantity FROM inventory WHERE id = %s', (product_id,))
        row = cursor.fetchone()
        
        if not row:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Product not found'}), 404
            
        quantity = row['quantity']
        if quantity > 0:
            new_quantity = quantity - 1
            cursor.execute('UPDATE inventory SET quantity = %s WHERE id = %s', (new_quantity, product_id))
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({'id': product_id, 'quantity': new_quantity})
        else:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Product is out of stock'}), 400
    except Exception as e:
        print("Error ordering product:", e)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3002)