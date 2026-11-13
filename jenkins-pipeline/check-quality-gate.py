import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

host = os.environ.get("SONAR_HOST_URL", "").rstrip("/")
token = os.environ.get("SONAR_TOKEN", "")
project = os.environ.get("SONAR_PROJECT_KEY", "book-my-date")
gate_timeout = int(os.environ.get("SONAR_GATE_TIMEOUT", "600"))

if not host:
    print("SonarQube host is not configured; skipping quality gate.")
    sys.exit(0)
if not token:
    print("ERROR: SONAR_TOKEN is not set.", file=sys.stderr)
    sys.exit(1)

query = urllib.parse.urlencode({"projectKey": project})
url = f"{host}/api/qualitygates/project_status?{query}"
headers = {"Authorization": f"Bearer {token}"}
deadline = time.time() + gate_timeout
last_status = None

while time.time() < deadline:
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        print(f"ERROR: SonarQube returned HTTP {exc.code}.", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Quality gate query failed: {exc}; retrying.", file=sys.stderr)
        time.sleep(10)
        continue

    project_status = payload.get("projectStatus", {})
    status = project_status.get("status", "UNKNOWN")
    if status != last_status:
        print(f"SonarQube quality gate status: {status}")
        last_status = status

    if status == "OK":
        sys.exit(0)
    if status == "ERROR":
        for condition in project_status.get("conditions", []):
            if condition.get("status") == "ERROR":
                metric = condition.get("metricKey", "unknown")
                actual = condition.get("actualValue", "n/a")
                threshold = condition.get("errorThreshold", "n/a")
                print(
                    f"FAILED: {metric}={actual} (threshold {threshold})",
                    file=sys.stderr,
                )
        sys.exit(1)

    time.sleep(10)

print(
    f"ERROR: quality gate did not complete within {gate_timeout} seconds.",
    file=sys.stderr,
)
sys.exit(1)
