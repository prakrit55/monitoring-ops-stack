helm repo add grafana https://grafana.github.io/helm-charts
helm repo add fluent https://fluent.github.io/helm-charts
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# 1. Deploy Grafana Loki
helm upgrade --install loki grafana/loki --namespace monitoring --create-namespace --values "R:\Devops territory\monitoring-ops-stack\logging\loki\helm-values\loki-values.yaml" --wait

# 2. Deploy Grafana Alloy (Option A)
helm upgrade --install alloy grafana/alloy --namespace monitoring --create-namespace --values "R:\Devops territory\monitoring-ops-stack\logging\loki\helm-values\alloy-values.yaml" --wait

# 3. Deploy Fluent Bit (Option B)
helm upgrade --install fluent-bit fluent/fluent-bit --namespace monitoring --create-namespace --values "R:\Devops territory\monitoring-ops-stack\logging\loki\helm-values\fluent-bit-values.yaml" --wait

# 4. Deploy Prometheus-Grafana stack
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack --version 72.6.2 --namespace monitoring --create-namespace --values "R:\Devops territory\monitoring-ops-stack\logging\loki\helm-values\prometheus-grafana-stack.yaml" --wait

# 5. Deploy OpenTelemetry Collector
helm upgrade --install opentelemetry-collector open-telemetry/opentelemetry-collector --namespace monitoring --create-namespace --values "R:\Devops territory\monitoring-ops-stack\logging\loki\helm-values\otel-loki-values.yaml" --wait
