import path from 'path';
import * as grpc from '@grpc/grpc-js';
import * as protoLoader from '@grpc/proto-loader';
import express, { Request, Response } from 'express';
import { MeterProvider, PeriodicExportingMetricReader } from '@opentelemetry/sdk-metrics';
import { OTLPMetricExporter } from '@opentelemetry/exporter-metrics-otlp-http';
import { Resource } from '@opentelemetry/resources';
import { SemanticResourceAttributes } from '@opentelemetry/semantic-conventions';

// Setup OpenTelemetry Metrics
const otelEndpoint = process.env.OTEL_EXPORTER_OTLP_ENDPOINT;
let meter: any = null;
let requestCounter: any = null;
let requestDuration: any = null;

if (otelEndpoint) {
  console.log(`Initializing OTLP metric exporter to ${otelEndpoint}`);
  const exporter = new OTLPMetricExporter({
    url: otelEndpoint.startsWith('http') ? `${otelEndpoint}/v1/metrics` : `http://${otelEndpoint}/v1/metrics`,
  });

  const meterProvider = new MeterProvider({
    resource: new Resource({
      [SemanticResourceAttributes.SERVICE_NAME]: 'service-c',
    }),
    readers: [
      new PeriodicExportingMetricReader({
        exporter: exporter,
        exportIntervalMillis: 15000,
      }),
    ],
  });

  meter = meterProvider.getMeter('service-c');
  requestCounter = meter.createCounter('http_requests_total', {
    description: 'Total number of HTTP requests received',
  });
  requestDuration = meter.createHistogram('http_request_duration_seconds', {
    description: 'Duration of HTTP requests in seconds',
    unit: 's',
  });
}

// Load Proto file
const PROTO_PATH = process.env.PROTO_PATH || path.join(__dirname, '../proto/service.proto');
const packageDefinition = protoLoader.loadSync(PROTO_PATH, {
  keepCase: true,
  longs: String,
  enums: String,
  defaults: true,
  oneofs: true,
});

const protoDescriptor = grpc.loadPackageDefinition(packageDefinition) as any;
const pb = protoDescriptor.pb;

const serviceAUrl = process.env.SERVICE_A_GRPC_URL || 'localhost:50051';
const serviceBUrl = process.env.SERVICE_B_GRPC_URL || 'localhost:50052';

const clientA = new pb.ServiceA(serviceAUrl, grpc.credentials.createInsecure());
const clientB = new pb.ServiceB(serviceBUrl, grpc.credentials.createInsecure());

const app = express();
const port = process.env.PORT || '8082';

app.use(express.json());

// Middleware for metrics instrumentation and CORS
app.use((req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, X-Correlation-Id');
  if (req.method === 'OPTIONS') {
    res.sendStatus(200);
    return;
  }

  const start = Date.now();
  res.on('finish', () => {
    const duration = (Date.now() - start) / 1000;
    const route = req.route ? req.route.path : req.path;
    if (requestCounter) {
      requestCounter.add(1, {
        'http.method': req.method,
        'http.route': route,
        'http.status_code': res.statusCode.toString(),
      });
    }
    if (requestDuration) {
      requestDuration.record(duration, {
        'http.method': req.method,
        'http.route': route,
        'http.status_code': res.statusCode.toString(),
      });
    }
  });
  next();
});

app.get('/', (req: Request, res: Response) => {
  res.json({ status: 'up', service: 'service-c' });
});

app.all('/call-grpc', (req: Request, res: Response) => {
  const name = req.body?.name || (req.query.name as string) || 'TypeScript Client';
  console.log(`Received request /call-grpc, calling Service A via gRPC at ${serviceAUrl}`);

  clientA.CallServiceA({ name: name }, (err: any, responseA: any) => {
    if (err) {
      console.error('Error calling Service A:', err);
      return res.status(502).json({ error: `Failed to call Service A: ${err.message}` });
    }

    console.log(`Received gRPC response from Service A:`, responseA);
    res.json({
      message: 'Hello from Service C (TypeScript)!',
      grpc_response_from_a: responseA,
    });
  });
});

app.listen(port, () => {
  console.log(`Service C (TypeScript) starting on port ${port}`);
});
