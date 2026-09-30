import 'dotenv/config';
import express from 'express';
import bodyParser from 'body-parser';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';
import os from 'os';
import client from 'prom-client';

const app = express();
app.use(bodyParser.json());
app.use(cors());

// Prometheus Metrics Configuration
const register = new client.Registry();
client.collectDefaultMetrics({ register, prefix: 'ecommerce_ui_' });

// Resource Usage Metrics (CPU, Memory, System Resources)
const processMemoryRssBytes = new client.Gauge({
  name: 'process_memory_rss_bytes',
  help: 'Resident Set Size (RSS) memory used by the process in bytes',
  registers: [register],
});

const processHeapUsedBytes = new client.Gauge({
  name: 'process_heap_used_bytes',
  help: 'Heap memory currently used by the Node.js process in bytes',
  registers: [register],
});

const systemMemoryFreeBytes = new client.Gauge({
  name: 'system_memory_free_bytes',
  help: 'Free system physical memory in bytes',
  registers: [register],
});

const systemMemoryTotalBytes = new client.Gauge({
  name: 'system_memory_total_bytes',
  help: 'Total system physical memory in bytes',
  registers: [register],
});

const systemCpuLoadAverage = new client.Gauge({
  name: 'system_cpu_load_average_1m',
  help: 'System CPU load average for the past 1 minute',
  registers: [register],
});

// HTTP Request Duration (Response Time / Latency in seconds)
const httpRequestDurationSeconds = new client.Histogram({
  name: 'http_request_duration_seconds',
  help: 'Duration of HTTP requests in seconds (response time & latency)',
  labelNames: ['method', 'route', 'status_code'],
  buckets: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
  registers: [register],
});

// HTTP Response Time (in milliseconds)
const httpResponseTimeMilliseconds = new client.Histogram({
  name: 'http_response_time_milliseconds',
  help: 'Total time taken to process a request and generate a response in milliseconds',
  labelNames: ['method', 'route', 'status_code'],
  buckets: [5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000],
  registers: [register],
});

// Total HTTP Requests Counter
const httpRequestsTotal = new client.Counter({
  name: 'http_requests_total',
  help: 'Total number of HTTP requests processed',
  labelNames: ['method', 'route', 'status_code'],
  registers: [register],
});

// Total HTTP Error Requests Counter (Error Rate Tracking)
const httpRequestsErrorsTotal = new client.Counter({
  name: 'http_requests_errors_total',
  help: 'Total number of HTTP requests that resulted in client (4xx) or server (5xx) errors',
  labelNames: ['method', 'route', 'status_code', 'error_type'],
  registers: [register],
});

// Service Exceptions & Operational Failures Counter
const serviceExceptionsTotal = new client.Counter({
  name: 'service_exceptions_total',
  help: 'Total number of internal exceptions and operational failures encountered',
  labelNames: ['exception_type', 'operation'],
  registers: [register],
});

// Downstream Service Calls Error Counter
export const downstreamServiceErrorsTotal = new client.Counter({
  name: 'downstream_service_errors_total',
  help: 'Total number of errors encountered when calling downstream microservices',
  labelNames: ['target_service', 'status_code', 'error_type'],
  registers: [register],
});

// Throughput: Active In-Flight Requests Gauge (Current Concurrent Gateway Load)
const httpRequestsInFlight = new client.Gauge({
  name: 'http_requests_in_flight',
  help: 'Current number of simultaneous active HTTP requests being processed (concurrency/load)',
  labelNames: ['route', 'method'],
  registers: [register],
});

// Helper function to resolve parameterized route template
function getRoutePattern(req) {
  if (req.route && req.route.path) {
    return (req.baseUrl || '') + req.route.path;
  }
  const pathname = req.path || '';
  if (pathname === '/api/signup') return '/api/signup';
  if (pathname === '/api/signin') return '/api/signin';
  if (pathname === '/api/profile') return '/api/profile';
  if (pathname === '/api/products') return '/api/products';
  if (/^\/api\/products\/[^/]+$/.test(pathname)) return '/api/products/:id';
  if (pathname === '/api/inventory') return '/api/inventory';
  if (/^\/api\/inventory\/[^/]+$/.test(pathname)) return '/api/inventory/:id';
  if (/^\/api\/orders\/[^/]+\/cart\/subtotal$/.test(pathname)) return '/api/orders/:userId/cart/subtotal';
  if (/^\/api\/orders\/[^/]+\/cart\/shipping$/.test(pathname)) return '/api/orders/:userId/cart/shipping';
  if (/^\/api\/orders\/[^/]+\/cart$/.test(pathname)) return '/api/orders/:userId/cart';
  if (/^\/api\/orders\/[^/]+\/purchase$/.test(pathname)) return '/api/orders/:userId/purchase';
  if (pathname === '/api/shipping-explanation') return '/api/shipping-explanation';
  if (pathname === '/api/all-shipping-fees') return '/api/all-shipping-fees';
  if (pathname === '/api/contact-message') return '/api/contact-message';
  if (pathname === '/api/contact-submit') return '/api/contact-submit';
  if (pathname === '/') return '/';
  return 'unmatched';
}

// Throughput: Response Payload Size in Bytes (Network throughput)
const httpResponseSizeBytes = new client.Histogram({
  name: 'http_response_size_bytes',
  help: 'Size of HTTP response payload in bytes (network throughput & bandwidth tracking)',
  labelNames: ['method', 'route', 'status_code'],
  buckets: [100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000],
  registers: [register],
});

// Latency, Response Time, Throughput & Error Rate Monitoring Middleware
app.use((req, res, next) => {
  if (req.path === '/metrics') {
    return next();
  }

  const initialRoute = getRoutePattern(req);
  const method = req.method;

  // Increment in-flight requests on entry
  httpRequestsInFlight.inc({ route: initialRoute, method });
  const startTime = process.hrtime.bigint();
  let decremented = false;

  const decrementInFlight = () => {
    if (!decremented) {
      decremented = true;
      httpRequestsInFlight.dec({ route: initialRoute, method });
    }
  };

  res.on('finish', () => {
    decrementInFlight();

    const endTime = process.hrtime.bigint();
    const durationMs = Number(endTime - startTime) / 1e6;
    const durationSec = durationMs / 1000;
    const route = getRoutePattern(req);
    const status = res.statusCode || 500;
    const statusCode = status.toString();

    // Latency & Response Time
    httpRequestDurationSeconds.observe({ method, route, status_code: statusCode }, durationSec);
    httpResponseTimeMilliseconds.observe({ method, route, status_code: statusCode }, durationMs);
    
    // Request Volume & Throughput
    httpRequestsTotal.inc({ method, route, status_code: statusCode });

    // Payload size throughput
    const contentLength = parseInt(res.getHeader('content-length'), 10);
    if (!isNaN(contentLength)) {
      httpResponseSizeBytes.observe({ method, route, status_code: statusCode }, contentLength);
    }

    // Track Error Rate (4xx and 5xx)
    if (status >= 400) {
      const errorType = status >= 500 ? 'server_error' : 'client_error';
      httpRequestsErrorsTotal.inc({ method, route, status_code: statusCode, error_type: errorType });
    }
  });

  // Prevent gauge leaks on client aborts/premature close
  res.on('close', () => {
    decrementInFlight();
  });

  next();
});

// Metrics endpoint for Prometheus scraping
app.get('/metrics', async (req, res) => {
  try {
    const memUsage = process.memoryUsage();
    processMemoryRssBytes.set(memUsage.rss);
    processHeapUsedBytes.set(memUsage.heapUsed);
    systemMemoryFreeBytes.set(os.freemem());
    systemMemoryTotalBytes.set(os.totalmem());
    const loadAvg = os.loadavg();
    if (loadAvg && loadAvg.length > 0) {
      systemCpuLoadAverage.set(loadAvg[0]);
    }

    res.set('Content-Type', register.contentType);
    res.end(await register.metrics());
  } catch (err) {
    res.status(500).end(err);
  }
});

// Get the directory name of the current module
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Serve the static files from the React app
app.use(express.static(path.join(__dirname, '../client/build')));

// API routes
import authRoutes from './routes/auth.js';
import productRoutes from './routes/products.js';
import inventoryRoutes from './routes/inventory.js';
import orderRoutes from './routes/orders.js';
import shippingRoutes from './routes/shipping.js';
import contactRoutes from './routes/contact.js';

app.use('/api', authRoutes);
app.use('/api', productRoutes);
app.use('/api', inventoryRoutes);
app.use('/api', orderRoutes);
app.use('/api', shippingRoutes);
app.use('/api', contactRoutes);

// Handle requests for the root URL
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, '../client/build', 'index.html'));
});

// Handle requests for other routes
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '../client/build', 'index.html'));
});

const port = process.env.PORT || 4000;
app.listen(port, () => {
  console.log(`Server is running on port ${port}`);
});