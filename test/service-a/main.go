package main

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net"
	"net/http"
	"os"
	"time"

	"go.opentelemetry.io/contrib/bridges/otelslog"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlplog/otlploghttp"
	"go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetrichttp"
	"go.opentelemetry.io/otel/log/global"
	"go.opentelemetry.io/otel/metric"
	sdklog "go.opentelemetry.io/otel/sdk/log"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	"go.opentelemetry.io/otel/sdk/resource"
	semconv "go.opentelemetry.io/otel/semconv/v1.24.0"

	"google.golang.org/grpc"
	"service-a/pb"
)

// MultiHandler forwards log records to multiple underlying slog Handlers.
type MultiHandler struct {
	handlers []slog.Handler
}

func (m *MultiHandler) Enabled(ctx context.Context, level slog.Level) bool {
	for _, h := range m.handlers {
		if h.Enabled(ctx, level) {
			return true
		}
	}
	return false
}

func (m *MultiHandler) Handle(ctx context.Context, r slog.Record) error {
	for _, h := range m.handlers {
		if h.Enabled(ctx, r.Level) {
			_ = h.Handle(ctx, r)
		}
	}
	return nil
}

func (m *MultiHandler) WithAttrs(attrs []slog.Attr) slog.Handler {
	newHandlers := make([]slog.Handler, len(m.handlers))
	for i, h := range m.handlers {
		newHandlers[i] = h.WithAttrs(attrs)
	}
	return &MultiHandler{handlers: newHandlers}
}

func (m *MultiHandler) WithGroup(name string) slog.Handler {
	newHandlers := make([]slog.Handler, len(m.handlers))
	for i, h := range m.handlers {
		newHandlers[i] = h.WithGroup(name)
	}
	return &MultiHandler{handlers: newHandlers}
}

func initLogger(serviceName string) (func(context.Context) error, slog.Handler) {
	// Console JSON Logger (Stdout)
	consoleHandler := slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	})

	otelEndpoint := os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
	if otelEndpoint == "" {
		slog.Info("OTEL_EXPORTER_OTLP_ENDPOINT not set; logging to stdout only")
		return func(ctx context.Context) error { return nil }, consoleHandler
	}

	ctx := context.Background()
	slog.Info("Initializing OTLP log exporter", "endpoint", otelEndpoint)

	exporter, err := otlploghttp.New(ctx,
		otlploghttp.WithEndpoint(otelEndpoint),
		otlploghttp.WithInsecure(),
	)
	if err != nil {
		slog.Error("failed to create OTLP log exporter, falling back to console only", "error", err)
		return func(ctx context.Context) error { return nil }, consoleHandler
	}

	res, err := resource.New(ctx,
		resource.WithAttributes(
			semconv.ServiceNameKey.String(serviceName),
		),
	)
	if err != nil {
		slog.Error("failed to create resource, falling back to console only", "error", err)
		return func(ctx context.Context) error { return nil }, consoleHandler
	}

	lp := sdklog.NewLoggerProvider(
		sdklog.WithProcessor(sdklog.NewBatchProcessor(exporter)),
		sdklog.WithResource(res),
	)
	global.SetLoggerProvider(lp)

	// Create the OTel slog handler
	otelHandler := otelslog.NewHandler(serviceName)

	// Combine stdout JSON and OTel handlers
	multiHandler := &MultiHandler{
		handlers: []slog.Handler{consoleHandler, otelHandler},
	}

	shutdown := func(shutdownCtx context.Context) error {
		return lp.Shutdown(shutdownCtx)
	}

	return shutdown, multiHandler
}

func generateCorrelationID() string {
	b := make([]byte, 16)
	_, err := rand.Read(b)
	if err != nil {
		return "fallback-id-" + fmt.Sprintf("%d", time.Now().UnixNano())
	}
	return hex.EncodeToString(b)
}

func main() {
	shutdown, handler := initLogger("service-a")
	defer func() {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := shutdown(ctx); err != nil {
			slog.Error("failed to shutdown logger provider", "error", err)
		}
	}()

	logger := slog.New(handler)
	slog.SetDefault(logger)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	serviceBURL := os.Getenv("SERVICE_B_URL")
	if serviceBURL == "" {
		serviceBURL = "http://localhost:8081/process"
	}

	otelEndpoint := os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
	metricsShutdown, err := initMetrics(context.Background(), "service-a", otelEndpoint)
	if err != nil {
		slog.Error("failed to initialize metrics", "error", err)
	} else {
		defer func() {
			ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			defer cancel()
			if err := metricsShutdown(ctx); err != nil {
				slog.Error("failed to shutdown meter provider", "error", err)
			}
		}()
	}

	meter := otel.Meter("service-a")

	http.HandleFunc("/", instrumentHandler(meter, func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"up","service":"service-a"}`))
	}, "/"))

	http.HandleFunc("/api/hello", instrumentHandler(meter, func(w http.ResponseWriter, r *http.Request) {
		correlationID := r.Header.Get("X-Correlation-Id")
		if correlationID == "" {
			correlationID = generateCorrelationID()
		}

		var name string = "Go Client"
		var bodyReader io.Reader = nil

		if r.Method == http.MethodPost {
			var body struct {
				Name string `json:"name"`
			}
			bodyBytes, err := io.ReadAll(r.Body)
			if err == nil {
				_ = json.Unmarshal(bodyBytes, &body)
				if body.Name != "" {
					name = body.Name
				}
				// Re-encode body bytes for service-b
				bodyReader = bytes.NewReader(bodyBytes)
			}
		} else {
			if n := r.URL.Query().Get("name"); n != "" {
				name = n
			}
		}

		slog.Info("received request to /api/hello",
			"correlation_id", correlationID,
			"method", r.Method,
			"path", r.URL.Path,
			"name", name,
			"client_ip", r.RemoteAddr,
			"user_agent", r.UserAgent(),
		)

		req, err := http.NewRequestWithContext(r.Context(), r.Method, serviceBURL, bodyReader)
		if err != nil {
			slog.Error("failed to create request to Service B",
				"correlation_id", correlationID,
				"error", err.Error(),
			)
			respondWithError(w, correlationID, "Internal creation error", http.StatusInternalServerError)
			return
		}
		
		// If POST, set Content-Type header
		if r.Method == http.MethodPost {
			req.Header.Set("Content-Type", "application/json")
		}
		req.Header.Set("X-Correlation-Id", correlationID)

		slog.Info("sending request to Service B",
			"correlation_id", correlationID,
			"method", r.Method,
			"url", serviceBURL,
		)

		client := &http.Client{
			Timeout: 5 * time.Second,
		}

		startTime := time.Now()
		resp, err := client.Do(req)
		duration := time.Since(startTime)

		if err != nil {
			slog.Error("failed to call Service B",
				"correlation_id", correlationID,
				"error", err.Error(),
				"duration_ms", duration.Milliseconds(),
			)
			respondWithError(w, correlationID, fmt.Sprintf("Failed to reach Service B: %v", err), http.StatusBadGateway)
			return
		}
		defer resp.Body.Close()

		slog.Info("received response from Service B",
			"correlation_id", correlationID,
			"status_code", resp.StatusCode,
			"duration_ms", duration.Milliseconds(),
		)

		body, err := io.ReadAll(resp.Body)
		if err != nil {
			slog.Error("failed to read response body from Service B",
				"correlation_id", correlationID,
				"error", err.Error(),
			)
			respondWithError(w, correlationID, "Failed to read Service B response", http.StatusInternalServerError)
			return
		}

		var bResponse interface{}
		if err := json.Unmarshal(body, &bResponse); err != nil {
			bResponse = string(body)
		}

		responsePayload := map[string]interface{}{
			"message":            fmt.Sprintf("Hello %s from Service A via HTTP (%s)!", name, r.Method),
			"correlation_id":     correlationID,
			"service_b_status":   resp.StatusCode,
			"service_b_response": bResponse,
			"duration_ms":        duration.Milliseconds(),
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(responsePayload)
	}, "/api/hello"))

	serviceBGrpcURL := os.Getenv("SERVICE_B_GRPC_URL")
	if serviceBGrpcURL == "" {
		serviceBGrpcURL = "localhost:50052"
	}

	// Start gRPC server
	lis, err := net.Listen("tcp", ":50051")
	if err != nil {
		slog.Error("failed to listen for gRPC", "error", err)
	} else {
		grpcServer := grpc.NewServer()
		pb.RegisterServiceAServer(grpcServer, &serviceAServer{serviceBGrpcURL: serviceBGrpcURL})
		go func() {
			slog.Info("Service A gRPC server starting", "port", "50051")
			if err := grpcServer.Serve(lis); err != nil {
				slog.Error("gRPC server failed", "error", err)
			}
		}()
	}

	slog.Info("Service A starting", "port", port, "service_b_url", serviceBURL)
	if err := http.ListenAndServe(":"+port, nil); err != nil {
		slog.Error("Service A failed to start", "error", err.Error())
		os.Exit(1)
	}
}

type serviceAServer struct {
	pb.UnimplementedServiceAServer
	serviceBGrpcURL string
}

func (s *serviceAServer) CallServiceA(ctx context.Context, req *pb.ServiceARequest) (*pb.ServiceAResponse, error) {
	correlationID := generateCorrelationID()
	slog.Info("received gRPC request to CallServiceA",
		"correlation_id", correlationID,
		"name", req.Name,
	)

	// Call Service B over gRPC
	slog.Info("sending gRPC request to Service B",
		"correlation_id", correlationID,
		"url", s.serviceBGrpcURL,
	)

	conn, err := grpc.Dial(s.serviceBGrpcURL, grpc.WithInsecure(), grpc.WithBlock(), grpc.WithTimeout(5*time.Second))
	var serviceBResponse string
	if err != nil {
		slog.Error("failed to connect to Service B gRPC", "error", err, "correlation_id", correlationID)
		serviceBResponse = fmt.Sprintf("Failed to reach Service B via gRPC: %v", err)
	} else {
		defer conn.Close()
		client := pb.NewServiceBClient(conn)
		resp, err := client.CallServiceB(ctx, &pb.ServiceBRequest{CorrelationId: correlationID})
		if err != nil {
			slog.Error("failed to call Service B gRPC", "error", err, "correlation_id", correlationID)
			serviceBResponse = fmt.Sprintf("Failed to call Service B: %v", err)
		} else {
			slog.Info("received gRPC response from Service B", "correlation_id", correlationID, "status", resp.Status)
			serviceBResponse = fmt.Sprintf("Success: processed by %s in %dms", resp.ProcessedBy, resp.LatencyMs)
		}
	}

	return &pb.ServiceAResponse{
		Message:          fmt.Sprintf("Hello %s from Service A via gRPC!", req.Name),
		CorrelationId:    correlationID,
		ServiceBResponse: serviceBResponse,
	}, nil
}

func respondWithError(w http.ResponseWriter, correlationID, msg string, code int) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(map[string]interface{}{
		"error":          msg,
		"correlation_id": correlationID,
	})
}

func initMetrics(ctx context.Context, serviceName, otelEndpoint string) (func(context.Context) error, error) {
	if otelEndpoint == "" {
		slog.Info("OTEL_EXPORTER_OTLP_ENDPOINT not set; metrics exporter disabled")
		return func(ctx context.Context) error { return nil }, nil
	}

	slog.Info("Initializing OTLP metric exporter", "endpoint", otelEndpoint)
	exporter, err := otlpmetrichttp.New(ctx,
		otlpmetrichttp.WithEndpoint(otelEndpoint),
		otlpmetrichttp.WithInsecure(),
	)
	if err != nil {
		return nil, err
	}

	res, err := resource.New(ctx,
		resource.WithAttributes(
			semconv.ServiceNameKey.String(serviceName),
		),
	)
	if err != nil {
		return nil, err
	}

	mp := sdkmetric.NewMeterProvider(
		sdkmetric.WithResource(res),
		sdkmetric.WithReader(sdkmetric.NewPeriodicReader(exporter, sdkmetric.WithInterval(15*time.Second))),
	)
	otel.SetMeterProvider(mp)

	return func(shutdownCtx context.Context) error {
		return mp.Shutdown(shutdownCtx)
	}, nil
}

type responseWriterWrapper struct {
	http.ResponseWriter
	statusCode int
}

func (rw *responseWriterWrapper) WriteHeader(code int) {
	rw.statusCode = code
	rw.ResponseWriter.WriteHeader(code)
}

func instrumentHandler(meter metric.Meter, next http.HandlerFunc, path string) http.HandlerFunc {
	requestCounter, err := meter.Int64Counter("http_requests_total",
		metric.WithDescription("Total number of HTTP requests received"),
		metric.WithUnit("1"),
	)
	if err != nil {
		slog.Error("failed to create request counter", "error", err)
	}

	requestDuration, err := meter.Float64Histogram("http_request_duration_seconds",
		metric.WithDescription("Duration of HTTP requests in seconds"),
		metric.WithUnit("s"),
	)
	if err != nil {
		slog.Error("failed to create request duration histogram", "error", err)
	}

	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, X-Correlation-Id")

		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}

		start := time.Now()
		rw := &responseWriterWrapper{ResponseWriter: w, statusCode: http.StatusOK}

		next(rw, r)

		duration := time.Since(start).Seconds()
		attrs := []attribute.KeyValue{
			attribute.String("http.method", r.Method),
			attribute.String("http.route", path),
			attribute.Int("http.status_code", rw.statusCode),
		}

		if requestCounter != nil {
			requestCounter.Add(r.Context(), 1, metric.WithAttributes(attrs...))
		}
		if requestDuration != nil {
			requestDuration.Record(r.Context(), duration, metric.WithAttributes(attrs...))
		}
	}
}
