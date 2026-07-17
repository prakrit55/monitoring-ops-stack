package main

import (
	"context"
	"encoding/json"
	"log/slog"
	"math/rand"
	"net/http"
	"os"
	"time"

	"go.opentelemetry.io/contrib/bridges/otelslog"
	"go.opentelemetry.io/otel/exporters/otlp/otlplog/otlploghttp"
	"go.opentelemetry.io/otel/log/global"
	sdklog "go.opentelemetry.io/otel/sdk/log"
	"go.opentelemetry.io/otel/sdk/resource"
	semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
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

func main() {
	shutdown, handler := initLogger("service-b")
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
		port = "8081"
	}

	// Seed local random generator
	r := rand.New(rand.NewSource(time.Now().UnixNano()))

	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"up","service":"service-b"}`))
	})

	http.HandleFunc("/process", func(w http.ResponseWriter, req *http.Request) {
		correlationID := req.Header.Get("X-Correlation-Id")
		if correlationID == "" {
			correlationID = "unknown"
		}

		slog.Info("Service B processing request started",
			"correlation_id", correlationID,
			"method", req.Method,
			"path", req.URL.Path,
		)

		// Simulate processing latency: 50ms - 250ms
		latency := time.Duration(50+r.Intn(200)) * time.Millisecond
		time.Sleep(latency)

		// Generate random logging behaviors to test Loki search/alerts
		chance := r.Float64()
		if chance < 0.05 { // 5% chance of severe error
			slog.Error("simulated database failure",
				"correlation_id", correlationID,
				"error", "connection refused by database pool",
				"table", "users",
			)
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusInternalServerError)
			_ = json.NewEncoder(w).Encode(map[string]interface{}{
				"status":         "error",
				"message":        "database transaction failed",
				"correlation_id": correlationID,
			})
			return
		}

		if chance < 0.20 { // 15% chance of warning
			slog.Warn("slow query performance warning",
				"correlation_id", correlationID,
				"latency_ms", latency.Milliseconds(),
				"query", "SELECT * FROM users WHERE status = 'active'",
			)
		}

		slog.Info("Service B processing request completed",
			"correlation_id", correlationID,
			"status", "success",
			"latency_ms", latency.Milliseconds(),
		)

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"status":         "success",
			"processed_by":   "service-b",
			"latency_ms":     latency.Milliseconds(),
			"correlation_id": correlationID,
		})
	})

	slog.Info("Service B starting", "port", port)
	if err := http.ListenAndServe(":"+port, nil); err != nil {
		slog.Error("Service B failed to start", "error", err.Error())
		os.Exit(1)
	}
}
