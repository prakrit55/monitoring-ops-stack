terraform {
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.0"
    }
  }
}

# 1. Create monitoring namespace
resource "kubernetes_namespace" "monitoring" {
  metadata {
    name = "monitoring"
  }
}

# 2. Deploy Prometheus + Grafana Stack
resource "helm_release" "prometheus_grafana_stack" {
  name       = "monitoring"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  version    = "72.6.2"
  namespace  = kubernetes_namespace.monitoring.metadata[0].name

  values = [
    file("${path.module}/../helm-values/prometheus-grafana-stack.yaml")
  ]
}

# 3. Deploy Tempo
resource "helm_release" "tempo" {
  name       = "tempo"
  repository = "https://grafana-community.github.io/helm-charts"
  chart      = "tempo"
  version    = "1.21.1"
  namespace  = kubernetes_namespace.monitoring.metadata[0].name

  values = [
    file("${path.module}/../helm-values/tempo-values.yaml")
  ]

  depends_on = [helm_release.prometheus_grafana_stack]
}

# 4. Deploy Alloy
resource "helm_release" "alloy" {
  name       = "alloy"
  repository = "https://grafana.github.io/helm-charts"
  chart      = "alloy"
  version    = "1.0.3"
  namespace  = kubernetes_namespace.monitoring.metadata[0].name

  values = [
    file("${path.module}/../helm-values/alloy-values.yaml")
  ]

  depends_on = [helm_release.tempo]
}
