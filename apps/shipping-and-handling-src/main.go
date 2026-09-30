package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
	"time"

	_ "github.com/lib/pq"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

var db *sql.DB

var (
	httpRequestDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "http_request_duration_seconds",
			Help:    "Duration of HTTP requests in seconds (response time & latency)",
			Buckets: []float64{0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0},
		},
		[]string{"method", "route", "status_code"},
	)

	httpResponseTimeMs = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "http_response_time_milliseconds",
			Help:    "Total time taken to process a request and generate a response in milliseconds",
			Buckets: []float64{5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000},
		},
		[]string{"method", "route", "status_code"},
	)

	httpRequestsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "http_requests_total",
			Help: "Total number of HTTP requests processed",
		},
		[]string{"method", "route", "status_code"},
	)

	httpRequestErrorsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "http_requests_errors_total",
			Help: "Total number of HTTP requests resulting in client (4xx) or server (5xx) errors",
		},
		[]string{"method", "route", "status_code", "error_type"},
	)

	serviceExceptionsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "service_exceptions_total",
			Help: "Total number of internal exceptions and operational failures encountered",
		},
		[]string{"exception_type", "operation"},
	)

	// Throughput: Active In-Flight Requests Gauge (Current Concurrent Load)
	httpRequestsInFlight = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "http_requests_in_flight",
			Help: "Current number of simultaneous active HTTP requests being processed (concurrency/load)",
		},
		[]string{"route", "method"},
	)

	// Throughput: Response Payload Size in Bytes (Network throughput)
	httpResponseSizeBytes = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "http_response_size_bytes",
			Help:    "Size of HTTP response payload in bytes (network throughput & bandwidth tracking)",
			Buckets: []float64{100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000},
		},
		[]string{"method", "route", "status_code"},
	)
)

type responseWriterWithStatus struct {
	http.ResponseWriter
	statusCode   int
	bytesWritten int64
}

func (rw *responseWriterWithStatus) WriteHeader(code int) {
	rw.statusCode = code
	rw.ResponseWriter.WriteHeader(code)
}

func (rw *responseWriterWithStatus) Write(b []byte) (int, error) {
	n, err := rw.ResponseWriter.Write(b)
	rw.bytesWritten += int64(n)
	return n, err
}

func prometheusMiddleware(next http.HandlerFunc, path string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		route := path
		if route == "" {
			route = "unmatched"
		}

		httpRequestsInFlight.WithLabelValues(route, r.Method).Inc()
		defer httpRequestsInFlight.WithLabelValues(route, r.Method).Dec()

		start := time.Now()
		wrapped := &responseWriterWithStatus{ResponseWriter: w, statusCode: http.StatusOK}

		next.ServeHTTP(wrapped, r)

		duration := time.Since(start)
		durationSec := duration.Seconds()
		durationMs := float64(duration.Milliseconds())
		statusStr := strconv.Itoa(wrapped.statusCode)

		httpRequestDuration.WithLabelValues(r.Method, route, statusStr).Observe(durationSec)
		httpResponseTimeMs.WithLabelValues(r.Method, route, statusStr).Observe(durationMs)
		httpRequestsTotal.WithLabelValues(r.Method, route, statusStr).Inc()
		httpResponseSizeBytes.WithLabelValues(r.Method, route, statusStr).Observe(float64(wrapped.bytesWritten))

		// Track Error Rate (4xx and 5xx)
		if wrapped.statusCode >= 400 {
			errorType := "client_error"
			if wrapped.statusCode >= 500 {
				errorType = "server_error"
			}
			httpRequestErrorsTotal.WithLabelValues(r.Method, route, statusStr, errorType).Inc()
		}
	}
}

func corsMiddleware(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// Set CORS headers
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "POST, GET, OPTIONS, PUT, DELETE")
		w.Header().Set("Access-Control-Allow-Headers", "Accept, Content-Type, Content-Length, Accept-Encoding, X-CSRF-Token, Authorization")

		// Pre-flight request
		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}

		next.ServeHTTP(w, r)
	}
}

// Product represents a product with an ID, name, description, price, and category.
type Product struct {
	ID          int     `json:"id"`
	Name        string  `json:"name"`
	Description string  `json:"description"`
	Price       float64 `json:"price"`
	Category    string  `json:"category"`
}

var defaultProducts = []Product{
	{ID: 1, Name: "Wireless Bluetooth Headphones", Description: "High-quality sound and comfortable fit", Price: 59.99, Category: "Electronics"},
	{ID: 2, Name: "Vintage Leather Backpack", Description: "Stylish and durable backpack for everyday use", Price: 89.99, Category: "Accessories"},
	{ID: 3, Name: "Stainless Steel Water Bottle", Description: "Eco-friendly and leak-proof water bottle", Price: 19.99, Category: "Home & Kitchen"},
	{ID: 4, Name: "Organic Green Tea", Description: "A refreshing and healthy organic green tea", Price: 15.99, Category: "Groceries"},
	{ID: 5, Name: "Smartwatch Fitness Tracker", Description: "Track your fitness and stay connected on the go", Price: 199.99, Category: "Electronics"},
	{ID: 6, Name: "Professional Studio Microphone", Description: "Record high-quality audio with this studio microphone", Price: 129.99, Category: "Electronics"},
	{ID: 7, Name: "Ergonomic Office Chair", Description: "Stay comfortable while working with this ergonomic chair", Price: 249.99, Category: "Office Supplies"},
	{ID: 8, Name: "LED Desk Lamp", Description: "Brighten your workspace with this energy-efficient LED lamp", Price: 39.99, Category: "Home & Kitchen"},
	{ID: 9, Name: "Gourmet Chocolate Box", Description: "Indulge in a variety of gourmet chocolates", Price: 29.99, Category: "Groceries"},
	{ID: 10, Name: "Yoga Mat with Carrying Strap", Description: "A non-slip yoga mat perfect for all types of yoga", Price: 49.99, Category: "Fitness"},
	{ID: 11, Name: "Insulated Camping Tent", Description: "A durable and insulated tent for your outdoor adventures", Price: 349.99, Category: "Outdoor"},
	{ID: 12, Name: "Bluetooth Speaker", Description: "Portable speaker with exceptional sound quality", Price: 99.99, Category: "Electronics"},
}

// calculateShippingFee calculates the shipping and handling fee based on the category of the product and time of day.
func calculateShippingFee(category string) float64 {
	baseFee := 5.0
	var categoryMultiplier float64
	timeOfDaySurcharge := 0.0
	peakHoursStart := 14 // 2 PM
	peakHoursEnd := 19   // 7 PM

	switch category {
	case "Electronics":
		categoryMultiplier = 2.0
	case "Office Supplies":
		categoryMultiplier = 1.8
	case "Home & Kitchen":
		categoryMultiplier = 1.5
	case "Groceries":
		categoryMultiplier = 1.2
	case "Fitness", "Outdoor":
		categoryMultiplier = 1.4
	default:
		categoryMultiplier = 1.0
	}

	currentHour := time.Now().Hour()

	if currentHour >= peakHoursStart && currentHour <= peakHoursEnd {
		timeOfDaySurcharge = 3.0
	}

	return baseFee * categoryMultiplier + timeOfDaySurcharge
}

func initDB() {
	host := os.Getenv("POSTGRES_HOST")
	if host == "" {
		host = "localhost"
	}
	port := os.Getenv("POSTGRES_PORT")
	if port == "" {
		port = "5432"
	}
	user := os.Getenv("POSTGRES_USER")
	if user == "" {
		user = "postgres"
	}
	password := os.Getenv("POSTGRES_PASSWORD")
	if password == "" {
		password = "postgres"
	}
	dbname := os.Getenv("POSTGRES_DB")
	if dbname == "" {
		dbname = "postgres"
	}

	psqlInfo := fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=disable",
		host, port, user, password, dbname)

	var err error
	db, err = sql.Open("postgres", psqlInfo)
	if err != nil {
		log.Fatalf("Error opening database: %q", err)
	}

	retries := 15
	for retries > 0 {
		err = db.Ping()
		if err == nil {
			break
		}
		retries--
		log.Printf("Failed to connect to PostgreSQL shipping db (retries left: %d): %q", retries, err)
		if retries == 0 {
			log.Println("Could not connect to database after all retries. Starting server anyway.")
			return
		}
		time.Sleep(3 * time.Second)
	}

	log.Println("Connected to PostgreSQL shipping db successfully")

	// Create table
	_, err = db.Exec(`
		CREATE TABLE IF NOT EXISTS shipping_fees (
			product_id INTEGER PRIMARY KEY,
			name VARCHAR(255) NOT NULL,
			description TEXT,
			price DOUBLE PRECISION NOT NULL,
			category VARCHAR(100) NOT NULL,
			shipping_fee DOUBLE PRECISION NOT NULL
		)
	`)
	if err != nil {
		log.Fatalf("Error creating table: %q", err)
	}

	// Seed data if empty
	var count int
	err = db.QueryRow("SELECT COUNT(*) FROM shipping_fees").Scan(&count)
	if err == nil && count == 0 {
		for _, p := range defaultProducts {
			fee := calculateShippingFee(p.Category)
			_, err = db.Exec(`
				INSERT INTO shipping_fees (product_id, name, description, price, category, shipping_fee)
				VALUES ($1, $2, $3, $4, $5, $6)
			`, p.ID, p.Name, p.Description, p.Price, p.Category, fee)
			if err != nil {
				log.Printf("Error seeding product %d: %q", p.ID, err)
			}
		}
		log.Println("Seeded shipping_fees table successfully")
	}
}

// handleShippingFee responds to the request with the calculated shipping fee for a product by its ID.
func handleShippingFee(w http.ResponseWriter, r *http.Request) {
	productID := r.URL.Query().Get("product_id")
	if productID == "" {
		http.Error(w, "Product ID is required", http.StatusBadRequest)
		return
	}

	if db == nil {
		http.Error(w, "Database not connected", http.StatusInternalServerError)
		return
	}

	var product struct {
		ID          int     `json:"id"`
		Name        string  `json:"name"`
		Description string  `json:"description"`
		Price       float64 `json:"price"`
		Category    string  `json:"category"`
		ShippingFee float64 `json:"shipping_fee"`
	}

	err := db.QueryRow(`
		SELECT product_id, name, description, price, category, shipping_fee
		FROM shipping_fees WHERE product_id = $1
	`, productID).Scan(&product.ID, &product.Name, &product.Description, &product.Price, &product.Category, &product.ShippingFee)

	if err != nil {
		if err == sql.ErrNoRows {
			http.Error(w, "Product not found", http.StatusNotFound)
		} else {
			http.Error(w, err.Error(), http.StatusInternalServerError)
		}
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(product)
}

// handleShippingExplanation provides a JSON object with explanation of the shipping fee calculation.
func handleShippingExplanation(w http.ResponseWriter, r *http.Request) {
	explanation := map[string]string{
		"explanation": "The shipping and handling fees are computed by employing a multi-tiered analytical framework. " +
			"The base fee is dynamically adjusted in accordance with the product's categorical classification. " +
			"This foundational fee is further compounded by a temporally variable surcharge applied during periods of " +
			"high demand, denoted as peak hours, which span from 2 PM to 7 PM. This intricate calculus ensures that the " +
			"fee structure robustly reflects both the logistical complexity inherent to the product's category and the " +
			"fluctuating operational demands associated with peak transactional intervals.",
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(explanation)
}

func handleAllShippingFees(w http.ResponseWriter, r *http.Request) {
	if db == nil {
		http.Error(w, "Database not connected", http.StatusInternalServerError)
		return
	}

	rows, err := db.Query(`
		SELECT product_id, name, description, price, category, shipping_fee
		FROM shipping_fees
	`)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	type FeeDetail struct {
		ProductID   int     `json:"product_id"`
		ShippingFee float64 `json:"shipping_fee"`
		Price       float64 `json:"price"`
		Name        string  `json:"name"`
		Description string  `json:"description"`
		Category    string  `json:"category"`
	}

	var feeDetails []FeeDetail
	for rows.Next() {
		var f FeeDetail
		err := rows.Scan(&f.ProductID, &f.Name, &f.Description, &f.Price, &f.Category, &f.ShippingFee)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		feeDetails = append(feeDetails, f)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(feeDetails)
}

func main() {
	initDB()
	if db != nil {
		defer db.Close()
	}

	http.Handle("/shipping-fee", corsMiddleware(prometheusMiddleware(handleShippingFee, "/shipping-fee")))
	http.Handle("/shipping-explanation", corsMiddleware(prometheusMiddleware(handleShippingExplanation, "/shipping-explanation")))
	http.Handle("/all-shipping-fees", corsMiddleware(prometheusMiddleware(handleAllShippingFees, "/all-shipping-fees")))
	http.Handle("/metrics", promhttp.Handler())

	fmt.Println("Server is running on port 8080...")
	log.Fatal(http.ListenAndServe(":8080", nil))
}