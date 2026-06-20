# LegacyAssured Backend Services

Welcome to the **LegacyAssured AI Backend** service repository. This service is a Flask-based application responsible for generating, managing, and storing user wills (including standard and Sharia-compliant wills), handling PDF generation, and integrating with Google Cloud Platform and Anthropic Claude LLM.

---

## 🚀 CI/CD Security & Deployment Pipeline

This repository is integrated with a secure, multi-stage GitHub Actions pipeline defined in [.github/workflows/main.yaml](file:///.github/workflows/main.yaml) that automatically runs on every push or pull request to the `main` branch.

### 📊 Pipeline Workflow Diagram

Here is a visual overview of how code progresses through the automated checks before deployment:

```mermaid
flowchart LR
    %% Styles and Node Definitions
    classDef trigger fill:#E1F5FE,stroke:#03A9F4,stroke-width:2px,color:#01579B;
    classDef setup fill:#EDE7F6,stroke:#673AB7,stroke-width:2px,color:#311B92;
    classDef quality fill:#FFF3E0,stroke:#FF9800,stroke-width:2px,color:#E65100;
    classDef security fill:#FFEBEE,stroke:#E91E63,stroke-width:2px,color:#880E4F;
    classDef deploy fill:#E8F5E9,stroke:#4CAF50,stroke-width:2px,color:#1B5E20;
    classDef fail fill:#FFEBEE,stroke:#F44336,stroke-width:2px,color:#B71C1C;

    subgraph Phase1 ["🐙 Trigger & Setup"]
        T1([💻 Push/PR]) ==> S1["📥 Checkout"] ==> S2["🐍 Python 3.14"] ==> S3["📦 Install & Cache"]
    end

    subgraph Phase2 ["🧪 Code Quality"]
        Q1["🧪 Run pytest"] ==> Q2{"📈 Pass Rate >= 85%?"}
        Q2 -- No ==> Q_FAIL[❌ Fail Build]
        Q2 -- Yes ==> Q3["🛡️ Bandit SAST"] ==> Q4["🔍 pip-audit SCA"]
    end

    subgraph Phase3 ["🐳 Container Security"]
        C1["🐳 Build Image"] ==> C2["🛡️ Trivy Scan"] ==> C3["🚀 Run Local App"] ==> C4["🛡️ ZAP DAST Scan"] ==> C5["📋 Save Reports"]
    end

    subgraph Phase4 ["🚀 Deploy"]
        D1["📤 Push Image"] ==> D2["🚀 Deploy Cloud Run"] ==> D3([🌐 Service Live])
    end

    %% Connections between phases
    S3 ==> Q1
    Q4 ==> C1
    C5 ==> D1

    %% Styling assignments
    class T1 trigger;
    class S1,S2,S3 setup;
    class Q1,Q2,Q3,Q4 quality;
    class Q_FAIL fail;
    class C1,C2,C3,C4,C5 security;
    class D1,D2,D3 deploy;
```

---

## 🛠️ Detailed Pipeline Stages

### Phase 1: Code Security & Unit Tests
1. **Checkout Repository**: Pulls the repository code into the GitHub runner workspace.
2. **Setup Python**: Configures a Python 3.14 environment with active `pip` dependency caching to speed up subsequent workflow runs.
3. **Install Dependencies**: Installs pip packages from `requirements.txt` alongside test tools (`pytest` and `bandit`).
4. **Pytest & Pass Threshold**: 
   - Runs the test suite under the `tests/` directory.
   - Generates a JUnit XML test report (`report.xml`).
   - Runs a custom validation script [.github/scripts/check_test_threshold.py](file:///.github/scripts/check_test_threshold.py) to assert that **at least 85% of tests pass**, allowing minor issues to pass while blocking major regressions.
5. **Dependency Vulnerability Audit (pip-audit)**: Audits dependencies for known security flaws and vulnerability warnings.
6. **Bandit Static Analysis (SAST)**: Performs static analysis scan on your Python files, excluding test scripts, pipelines, and virtual environments (`venv`) to identify security code flaws. The report is saved as `bandit-report.html`.

### Phase 2: Build & Container Audits
7. **Authenticate with GCP**: Uses Google service account credentials (`GCP_SA_KEY`) to log into Google Cloud Platform.
8. **Configure Cloud SDK & Docker**: Logs Docker daemon into Google Artifact Registry at `europe-west1-docker.pkg.dev`.
9. **Build Docker Image**: Compiles a production-ready container image using the `Dockerfile` with standard SHA and `latest` tags.
10. **Trivy Container Scan**: Runs security scans on the built Docker image for operating system and package library flaws. The build will fail if any **CRITICAL** or **HIGH** severity issues with available patches are found.
11. **OWASP ZAP Dynamic Scan (DAST)**:
    - Spins up the built Docker container locally on port `5000:5000`.
    - Polls the `/health` endpoint until the container is ready.
    - Runs a passive ZAP baseline scan (`zaproxy/zap-stable`) against the running service, outputting `zap_report.html`.
    - Automatically stops and cleans up the container (via a shell `trap`).
    - Uploads the security report as a download-friendly workflow artifact.

### Phase 3: Verify & Deploy
12. **Push Docker Image**: Verified Docker images are pushed to Google Artifact Registry.
13. **Deploy to GCP Cloud Run**: Deploys the service to Google Cloud Run, retrieving service-specific secrets (such as API keys and MongoDB strings) on the fly from Google Secret Manager (`app-secrets-prod-la1`).

---

## 📂 Project Structure

```
LegacyAssured-AIBackend/
├── .github/
│   ├── scripts/
│   │   └── check_test_threshold.py  # Test pass-rate validator (>= 85%)
│   └── workflows/
│       └── main.yaml                # CI/CD deployment configuration
├── tests/                           # Python Test Suite
│   ├── test_app.py                  # API routes integration tests (mock-based)
│   ├── test_health.py               # Flask health endpoint check
│   ├── test_merge.py                # Preprocessor merging logic tests
│   └── test_utils.py                # Serialization helper tests
├── will_service/                    # Core Business Logic Module
│   ├── core/                        # PDF generation & legal jurisdiction rules
│   ├── data_access/                 # MongoDB service wrappers
│   ├── preprocessing/               # Will details merging preprocessor
│   ├── services/                    # LLM (Anthropic) & GCS clients
│   └── utils/                       # Serialization & date utilities
├── app.py                           # Flask server entry point & endpoints
├── Dockerfile                       # Multi-stage production container definition
└── requirements.txt                 # Python application dependencies
```

---

## 🧪 Testing the Application Locally

You can run the tests and examine code coverage locally using:
```powershell
# Install test requirements
pip install pytest pytest-cov

# Run pytest with code coverage tracking
python -m pytest tests/ -v --cov=app --cov=will_service
```
