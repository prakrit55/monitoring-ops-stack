const express = require('express');
const bodyParser = require('body-parser');
const cors = require('cors');
const { MongoClient } = require('mongodb');
const redis = require('redis');
const os = require('os');
const client = require('prom-client');

const app = express();
app.use(bodyParser.json());
app.use(cors());

// Prometheus Metrics Configuration
const register = new client.Registry();
client.collectDefaultMetrics({ register, prefix: 'product_catalog_' });
 
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

// Throughput: Active In-Flight Requests Gauge (Current Concurrent Load)
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
  if (pathname === '/api/products') return '/api/products';
  if (/^\/api\/products\/[^/]+$/.test(pathname)) return '/api/products/:id';
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

const MONGODB_URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/product_catalog';
const REDIS_URL = process.env.REDIS_URL || 'redis://localhost:6379';

let dbClient;
let productsCollection;
let redisClient;

// Default products to seed the database if empty
const defaultProducts = [
  {
    id: 1,
    name: 'Wireless Bluetooth Headphones',
    description: 'High-quality sound and comfortable fit',
    price: 59.99,
    category: 'Electronics',
  },
  {
    id: 2,
    name: 'Vintage Leather Backpack',
    description: 'Stylish and durable backpack for everyday use',
    price: 89.99,
    category: 'Accessories',
  },
  {
    id: 3,
    name: 'Stainless Steel Water Bottle',
    description: 'Eco-friendly and leak-proof water bottle',
    price: 19.99,
    category: 'Home & Kitchen',
  },
  {
    id: 4,
    name: 'Organic Green Tea',
    description: 'A refreshing and healthy organic green tea',
    price: 15.99,
    category: 'Groceries',
  },
  {
    id: 5,
    name: 'Smartwatch Fitness Tracker',
    description: 'Track your fitness and stay connected on the go',
    price: 199.99,
    category: 'Electronics',
  },
  {
    id: 6,
    name: 'Professional Studio Microphone',
    description: 'Record high-quality audio with this studio microphone',
    price: 129.99,
    category: 'Electronics',
  },
  {
    id: 7,
    name: 'Ergonomic Office Chair',
    description: 'Stay comfortable while working with this ergonomic chair',
    price: 249.99,
    category: 'Office Supplies',
  },
  {
    id: 8,
    name: 'LED Desk Lamp',
    description: 'Brighten your workspace with this energy-efficient LED lamp',
    price: 39.99,
    category: 'Home & Kitchen',
  },
  {
    id: 9,
    name: 'Gourmet Chocolate Box',
    description: 'Indulge in a variety of gourmet chocolates',
    price: 29.99,
    category: 'Groceries',
  },
  {
    id: 10,
    name: 'Yoga Mat with Carrying Strap',
    description: 'A non-slip yoga mat perfect for all types of yoga',
    price: 49.99,
    category: 'Fitness',
  },
  {
    id: 11,
    name: 'Insulated Camping Tent',
    description: 'A durable and insulated tent for your outdoor adventures',
    price: 349.99,
    category: 'Outdoor',
  },
  {
    id: 12,
    name: 'Bluetooth Speaker',
    description: 'Portable speaker with exceptional sound quality',
    price: 99.99,
    category: 'Electronics',
  }
];

async function connectDB() {
  try {
    dbClient = new MongoClient(MONGODB_URI);
    await dbClient.connect();
    const db = dbClient.db();
    productsCollection = db.collection('products');
    console.log('Connected to MongoDB database');

    // Seed data if empty
    const count = await productsCollection.countDocuments();
    if (count === 0) {
      await productsCollection.insertMany(defaultProducts);
      console.log('Seeded database with default products');
    }
  } catch (error) {
    console.error('Failed to connect to MongoDB:', error);
  }
}

async function connectRedis() {
  try {
    redisClient = redis.createClient({ url: REDIS_URL });
    redisClient.on('error', (err) => console.error('Redis Client Error', err));
    await redisClient.connect();
    console.log('Connected to Redis server');
  } catch (error) {
    console.error('Failed to connect to Redis:', error);
  }
}

// Get all products
app.get('/api/products', async (req, res) => {
  try {
    // 1. Try serving from Redis cache
    if (redisClient && redisClient.isOpen) {
      try {
        const cachedCatalog = await redisClient.get('catalog:all');
        if (cachedCatalog) {
          console.log('Serving catalog from Redis cache');
          return res.json(JSON.parse(cachedCatalog));
        }
      } catch (cacheError) {
        console.error('Redis get error:', cacheError);
      }
    }

    // 2. Fetch from MongoDB database
    if (!productsCollection) {
      return res.status(500).json({ error: 'Database connection not established' });
    }
    const products = await productsCollection.find({}).project({ _id: 0 }).toArray();
    console.log('Serving catalog from MongoDB');

    // 3. Cache the catalog in Redis (TTL: 5 minutes / 300 seconds)
    if (redisClient && redisClient.isOpen) {
      try {
        await redisClient.setEx('catalog:all', 300, JSON.stringify(products));
      } catch (cacheError) {
        console.error('Redis set error:', cacheError);
      }
    }

    res.json(products);
  } catch (error) {
    console.error('Error fetching products:', error);
    res.status(500).json({ error: 'Error fetching products' });
  }
});

// Get a single product by ID
app.get('/api/products/:id', async (req, res) => {
  try {
    const productId = parseInt(req.params.id);
    const cacheKey = `product:id:${productId}`;

    // 1. Try serving from Redis cache
    if (redisClient && redisClient.isOpen) {
      try {
        const cachedProduct = await redisClient.get(cacheKey);
        if (cachedProduct) {
          console.log(`Serving product ${productId} from Redis cache`);
          return res.json(JSON.parse(cachedProduct));
        }
      } catch (cacheError) {
        console.error('Redis get error:', cacheError);
      }
    }

    // 2. Fetch from MongoDB database
    if (!productsCollection) {
      return res.status(500).json({ error: 'Database connection not established' });
    }
    const product = await productsCollection.findOne({ id: productId }, { projection: { _id: 0 } });

    if (product) {
      console.log(`Serving product ${productId} from MongoDB`);
      // 3. Cache the product details in Redis (TTL: 5 minutes / 300 seconds)
      if (redisClient && redisClient.isOpen) {
        try {
          await redisClient.setEx(cacheKey, 300, JSON.stringify(product));
        } catch (cacheError) {
          console.error('Redis set error:', cacheError);
        }
      }
      res.json(product);
    } else {
      res.status(404).json({ error: 'Product not found' });
    }
  } catch (error) {
    console.error('Error fetching product:', error);
    res.status(500).json({ error: 'Error fetching product' });
  }
});

// Start the server
const port = process.env.PORT || 3001;
async function startServer() {
  await connectDB();
  await connectRedis();
  app.listen(port, () => {
    console.log(`Product Catalog microservice is running on port ${port}`);
  });
}

startServer();