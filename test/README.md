# Loki Logging Test: Interconnected Go Applications

This test suite consists of two lightweight, containerized Go applications (`service-a` and `service-b`) designed to demonstrate end-to-end log flow, structured JSON logging, and cross-service request correlation in Grafana Loki.

## Architecture & Log Correlation Flow

```
   [ Client Request ]
           │
           ▼
┌──────────────────────┐ (Port 8080)
│      service-a       │ ──► Generates or propagates X-Correlation-Id
└──────────────────────┘ ──► Logs incoming request (JSON format)
           │
           ▼ (HTTP GET /process with X-Correlation-Id)
┌──────────────────────┐ (Port 8081)
│      service-b       │ ──► Extracts X-Correlation-Id
└──────────────────────┘ ──► Performs work & logs execution status (INFO/WARN/ERROR)
           │
           ▼ (JSON response)
┌──────────────────────┐
│      service-a       │ ──► Logs downstream response details & returns result
└──────────────────────┘
```

By passing a unified `correlation_id` in the JSON logs of both services, you can trace a single request's complete lifecycle across service boundaries using Grafana Loki.

---

## 1. Local Testing (Without Kubernetes/Docker)

You can run these applications locally to verify logging formats and standard behaviour.

### Run Service B
```bash
cd service-b
$env:OTEL_EXPORTER_OTLP_ENDPOINT="localhost:4318"  # Set to stream logs to OTel collector over OTLP/HTTP
# Or on Unix:
# export OTEL_EXPORTER_OTLP_ENDPOINT="localhost:4318"
go run main.go
```
*Starts on port `8081` by default.*

### Run Service A
```bash
cd service-a
# Configure Service A to point to Service B and optionally the local OTel Collector
$env:SERVICE_B_URL="http://localhost:8081/process"
$env:OTEL_EXPORTER_OTLP_ENDPOINT="localhost:4318"  # Set to stream logs to OTel collector over OTLP/HTTP
# Or on Unix:
# export SERVICE_B_URL="http://localhost:8081/process"
# export OTEL_EXPORTER_OTLP_ENDPOINT="localhost:4318"
go run main.go
```
*Starts on port `8080` by default.*

### Send a Test Request
Open a new terminal and send an HTTP request:
```bash
curl http://localhost:8080/api/hello
```

**Expected JSON Response:**
```json
{
  "correlation_id": "8c414995f5195cc4b5b487c603b55c39",
  "duration_ms": 152,
  "message": "Hello from Service A!",
  "service_b_response": {
    "correlation_id": "8c414995f5195cc4b5b487c603b55c39",
    "latency_ms": 150,
    "processed_by": "service-b",
    "status": "success"
  },
  "service_b_status": 200
}
```

**Stdout Log Samples (JSON Format):**
```json
{"time":"2026-07-17T16:50:00.000Z","level":"INFO","msg":"received request to /api/hello","correlation_id":"8c414995f5195cc4b5b487c603b55c39","method":"GET","path":"/api/hello","client_ip":"127.0.0.1:51234","user_agent":"curl/7.81.0"}
{"time":"2026-07-17T16:50:00.000Z","level":"INFO","msg":"Service B processing request started","correlation_id":"8c414995f5195cc4b5b487c603b55c39","method":"GET","path":"/process"}
{"time":"2026-07-17T16:50:00.150Z","level":"INFO","msg":"Service B processing request completed","correlation_id":"8c414995f5195cc4b5b487c603b55c39","status":"success","latency_ms":150}
{"time":"2026-07-17T16:50:00.152Z","level":"INFO","msg":"received response from Service B","correlation_id":"8c414995f5195cc4b5b487c603b55c39","status_code":200,"duration_ms":152}
```

---

## 2. Deploying to Kubernetes

### Create Google Artifact Registry (GAR) Repositories

Create two dedicated Docker repositories in Google Artifact Registry (one for each service):

```bash
gcloud artifacts repositories create service-a --repository-format=docker --location=us-central1 --description="Docker repository for service-a logs testing app"
gcloud artifacts repositories create service-b --repository-format=docker --location=us-central1 --description="Docker repository for service-b logs testing app"
```

### Build and Push to Google Artifact Registry (GAR)

Configure docker authentication with the registry location:
```bash
gcloud auth configure-docker us-central1-docker.pkg.dev
```

Define configuration variables:
```bash
# PowerShell
$LOCATION="us-central1"
$PROJECT="k8s-staging-252732"

# Bash
LOCATION="us-central1"
PROJECT="k8s-staging-252732"
```

Build, tag, and push the docker images to their respective repositories:
```bash
# Service A
docker build -t ${LOCATION}-docker.pkg.dev/${PROJECT}/service-a/service-a:latest ./service-a
docker push ${LOCATION}-docker.pkg.dev/${PROJECT}/service-a/service-a:latest

# Service B
docker build -t ${LOCATION}-docker.pkg.dev/${PROJECT}/service-b/service-b:latest ./service-b
docker push ${LOCATION}-docker.pkg.dev/${PROJECT}/service-b/service-b:latest
```

### Automating Build & Push with GitHub Actions

A GitHub Actions workflow is configured in [.github/workflows/loki-test-apps.yaml](file:///R:/Devops%20territory/monitoring-ops-stack/.github/workflows/loki-test-apps.yaml) to automate builds on changes to the test apps.

Since service account key creation is restricted in this project by the organization policy constraint `constraints/iam.disableServiceAccountKeyCreation`, authentication is configured via **Workload Identity Federation (WIF)**.

To configure and run the workflow:

1. **Set up Workload Identity Federation**:
   Run the following commands to create the service account, configure the Workload Identity Pool and Provider, and authorize your GitHub Actions workflow:
   ```bash
   # 1. Create the service account and assign Artifact Registry permissions
   gcloud iam service-accounts create loki-test-pusher --display-name="Loki Test Apps Pusher"
   gcloud projects add-iam-policy-binding k8s-staging-252732 --member="serviceAccount:loki-test-pusher@k8s-staging-252732.iam.gserviceaccount.com" --role="roles/artifactregistry.writer"

   # 2. Create the Workload Identity Pool
   gcloud iam workload-identity-pools create loki-test-pool --location="global" --display-name="Loki Test Pool"

   # 3. Create the OIDC Workload Identity Provider for GitHub Actions (restricting to your repository)
   gcloud iam workload-identity-pools providers create-oidc github-provider \
       --workload-identity-pool="loki-test-pool" \
       --location="global" \
       --issuer-uri="https://token.actions.githubusercontent.com" \
       --attribute-mapping="google.subject=assertion.subject,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
       --attribute-condition="assertion.repository == 'prakrit55/monitoring-ops-stack'" \
       --display-name="GitHub Provider"

   # 4. Get the project number automatically (which resolves to 898698082979)
   PROJECT_NUMBER=$(gcloud projects describe k8s-staging-252732 --format="value(projectNumber)")

   # 5. Authorize the GitHub repository to impersonate the service account
   gcloud iam service-accounts add-iam-policy-binding loki-test-pusher@k8s-staging-252732.iam.gserviceaccount.com \
       --role="roles/iam.workloadIdentityUser" \
       --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/loki-test-pool/attribute.repository/prakrit55/monitoring-ops-stack"
   ```

2. **Workflow Pre-configuration**:
   - The workflow file [.github/workflows/loki-test-apps.yaml](file:///R:/Devops%20territory/monitoring-ops-stack/.github/workflows/loki-test-apps.yaml) is pre-configured with the target Workload Identity Provider (`projects/898698082979/...`) and Service Account email (`loki-test-pusher@k8s-staging-252732...`).
   - No GitHub secrets need to be added.

3. **Triggering**:
   - The workflow automatically runs when files inside `logging/loki/test/` are pushed to the repository.
   - You can also manually trigger it via the **Actions** tab using the `workflow_dispatch` button.

### Apply Manifests

Deploy the applications to your GKE or Kubernetes cluster under the `monitoring` namespace using Kustomize (which dynamically compiles the local Helm charts for each service):

```bash
# Make sure you are in the test/ directory
kubectl apply -k . --enable-helm
```

Verify the pods are running:
```bash
kubectl get pods -n monitoring -l "app in (service-a, service-b)"
```

### Access and Generate Logs in K8s
Port-forward `service-a` to make it accessible locally:
```bash
kubectl port-forward svc/service-a 8080:8080 -n monitoring
```

Now hit the endpoint multiple times to populate logs:
```bash
for i in {1..10}; do curl http://localhost:8080/api/hello; echo ""; sleep 1; done
```

---

## 3. Querying Logs in Grafana / Loki

Open Grafana and navigate to the **Explore** tab, selecting the **Loki** datasource.

### Query Logs for a Specific Service
To view logs from Service A:
```logql
{container="service-a"}
```

To view logs from Service B:
```logql
{container="service-b"}
```

### Parse JSON Logs Automatically
Loki can parse structured JSON logs using the `json` stage:
```logql
{container="service-a"} | json
```
Once parsed, fields like `correlation_id`, `duration_ms`, `level`, and `msg` are populated as labels on the fly.

### Filter by Log Level
To find only warning or error logs in Service B:
```logql
{container="service-b"} | json | level=~"WARN|ERROR"
```

### Correlate Requests Across Services
Copy a `correlation_id` from a Service A log entry and query both services to trace the request cycle:
```logql
{container=~"service-.*"} | json | correlation_id="<YOUR-CORRELATION-ID-HERE>"
```
This shows the sequence of events starting at Service A, processing in Service B, and finishing back in Service A.
