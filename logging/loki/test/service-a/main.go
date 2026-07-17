package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
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

	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"up","service":"service-a"}`))
	})

	http.HandleFunc("/api/hello", func(w http.ResponseWriter, r *http.Request) {
		correlationID := r.Header.Get("X-Correlation-Id")
		if correlationID == "" {
			correlationID = generateCorrelationID()
		}

		slog.Info("received request to /api/hello",
			"correlation_id", correlationID,
			"method", r.Method,
			"path", r.URL.Path,
			"client_ip", r.RemoteAddr,
			"user_agent", r.UserAgent(),
		)

		req, err := http.NewRequestWithContext(r.Context(), "GET", serviceBURL, nil)
		if err != nil {
			slog.Error("failed to create request to Service B",
				"correlation_id", correlationID,
				"error", err.Error(),
			)
			respondWithError(w, correlationID, "Internal creation error", http.StatusInternalServerError)
			return
		}
		req.Header.Set("X-Correlation-Id", correlationID)

		slog.Info("sending request to Service B",
			"correlation_id", correlationID,
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
			"message":            "Hello from Service A!",
			"correlation_id":     correlationID,
			"service_b_status":   resp.StatusCode,
			"service_b_response": bResponse,
			"duration_ms":        duration.Milliseconds(),
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(responsePayload)
	})

	slog.Info("Service A starting", "port", port, "service_b_url", serviceBURL)
	if err := http.ListenAndServe(":"+port, nil); err != nil {
		slog.Error("Service A failed to start", "error", err.Error())
		os.Exit(1)
	}
}

func respondWithError(w http.ResponseWriter, correlationID, msg string, code int) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(map[string]interface{}{
		"error":          msg,
		"correlation_id": correlationID,
	})
}
