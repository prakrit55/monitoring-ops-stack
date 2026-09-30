#!/usr/bin/env python3
"""
Deploy/Overwrite Dashboard to Grafana via REST API
Usage: python deploy-dashboard.py [grafana_url] [username] [password]
Default: http://localhost:3000 admin admin
"""

import sys
import json
import base64
import urllib.request
import urllib.error

GRAFANA_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3000"
USER = sys.argv[2] if len(sys.argv) > 2 else "admin"
PASSWORD = sys.argv[3] if len(sys.argv) > 3 else "admin"
DASHBOARD_PATH = "dashboards/tier2-route-drilldown.json"

def deploy():
    print(f"Loading dashboard from {DASHBOARD_PATH}...")
    with open(DASHBOARD_PATH, "r", encoding="utf-8") as f:
        dashboard_json = json.load(f)

    # Ensure overwrite is true and reset ID if needed
    payload = {
        "dashboard": dashboard_json,
        "overwrite": True,
        "message": "Automated deployment of Tier 2 Route Drilldown Dashboard"
    }

    url = f"{GRAFANA_URL.rstrip('/')}/api/dashboards/db"
    auth_header = "Basic " + base64.b64encode(f"{USER}:{PASSWORD}".encode("utf-8")).decode("utf-8")

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": auth_header
        },
        method="POST"
    )

    try:
        print(f"Pushing to Grafana API at {url}...")
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            print("Successfully deployed dashboard to Grafana!")
            print(f"Status: {res_data.get('status')}")
            print(f"Dashboard URL: {GRAFANA_URL.rstrip('/')}{res_data.get('url')}")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.read().decode('utf-8')}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Connection Error: {e.reason}")
        print(f"Please ensure Grafana is reachable at {GRAFANA_URL}")
        sys.exit(1)

if __name__ == "__main__":
    deploy()
